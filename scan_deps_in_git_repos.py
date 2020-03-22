#!/usr/bin/env python3

#Copyright 2020 Dominique Gückel

#Licensed under the Apache License, Version 2.0 (the "License");
#you may not use this file except in compliance with the License.
#You may obtain a copy of the License at

    #http://www.apache.org/licenses/LICENSE-2.0

#Unless required by applicable law or agreed to in writing, software
#distributed under the License is distributed on an "AS IS" BASIS,
#WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#See the License for the specific language governing permissions and
#limitations under the License.

import os
import argparse
import pathlib
import sys
import subprocess
from subprocess import PIPE
import sqlite3

SUBPROCESS_OUTPUT_ENCODING = 'utf-8'
FILE_NAME_OF_GITMODULES_FILE = ".gitmodules"

LINE_PREFIX_SUBMODULE_SECTION_START = "[submodule"
LINE_PREFIX_PATH = "path"
LINE_PREFIX_URL = "url"

DATABASE_FILE_NAME = "gitproject_dependency_database.db"
PATH_TO_DML_QUERY_FOR_SOURCE_PROJECT_BY_NAME = "dml/queryForSourceCodeProjectByName.sql"
PATH_TO_DML_COMMAND_FOR_INSERTING_NEW_SOURCE_PROJECT = "dml/cmdForInsertingNewProject.sql"
PATH_TO_DML_COMMAND_FOR_INSERTING_DEPENDS_ON_RELATION = "dml/cmdForInsertingDependsOnRelation.sql"

queryForSourceCodeProjectByName = ""
sqlCmdForInsertingNewProject = ""
sqlCmdForInsertingDependsOnRelation = ""


class GitSubModule:
    name = ""
    path = ""
    url = ""
    
    def __init__(self, name = "", path = "", url = ""):
        self.name = name
        self.path = path
        self.url = url
        
    def isComplete(self):
        return self.name != "" and self.path != "" and self.url != ""
    
    def getProjectNameFromUrl(self):
        parts = self.url.rpartition("/")
        projectName = parts[2]
        projectName = projectName.replace(".git", "").strip()
        return projectName
        

def createArgumentParser():
    parser = argparse.ArgumentParser(description="Scans Git repositories for their submodule dependencies and collects the result.")
    parser.add_argument("-d", "--directory", 
        dest = "directory",
        action = "store", 
        default = ".",
        help = "The directory to examine. If used without the parameter \"-r\", this directory is assumed to indicate a Git repository. Default: current directory.")
    parser.add_argument("-a", "--all-dirs-in",
        dest="allDirectoriesInPath",
        action="store_const",
        const = True,
        default = False,
        help = "Interpret the value of \"-d\" not as a directory containing a Git repository itself but as a directory that *contains* directories, each of which might be a Git repository. These directories are then tested whether they are actually Git repositories, and if so, they are handled as if each of them were called as the value of the parameter \"-d\".")
    return parser

def prepareSqlStatementFromFile(pathToFile):
    statementFromFile = ""
    with open(pathToFile, 'r') as inputFile:
        statementFromFile = inputFile.read()
    statementFromFile = statementFromFile.replace("\n", " ")
    return statementFromFile

def prepareSqlStatements():
    global queryForSourceCodeProjectByName
    queryForSourceCodeProjectByName = prepareSqlStatementFromFile(PATH_TO_DML_QUERY_FOR_SOURCE_PROJECT_BY_NAME)
    global sqlCmdForInsertingNewProject 
    sqlCmdForInsertingNewProject = prepareSqlStatementFromFile(PATH_TO_DML_COMMAND_FOR_INSERTING_NEW_SOURCE_PROJECT)
    global sqlCmdForInsertingDependsOnRelation
    sqlCmdForInsertingDependsOnRelation = prepareSqlStatementFromFile(PATH_TO_DML_COMMAND_FOR_INSERTING_DEPENDS_ON_RELATION)

def analyzeRepositoryRootDir(pathToFolder, dbConnection):
    print("Scanning", pathToFolder, "for Git repositories")
    if not os.path.exists(pathToFolder):
        raise FileNotFoundError("Error: folder " + pathToFolder + " does not exist.")
    if not os.path.isdir(pathToFolder):
        raise NotADirectoryError("The argument is not a directory")
    for directoryEntry in os.listdir(pathToFolder):
        absPathToDir = os.path.abspath(os.path.join(pathToFolder, directoryEntry))
        if os.path.isdir(absPathToDir):
            analyzeGitRepository(absPathToDir, dbConnection)

def isGitRepository(absolutePathToObject):
    os.chdir(absolutePathToObject)
    process = subprocess.run(["git", "rev-parse", "--show-toplevel"], stdout=PIPE, stderr=PIPE)
    return process.returncode == 0

def isEmptyFolder(pathToFolder):
    if not os.path.exists(pathToFolder):
        raise FileNotFoundError("Error: folder " + pathToFolder + " does not exist.")
    if not os.path.isdir(pathToFolder):
        raise NotADirectoryError("The argument is not a directory")
    numberOfFilesInFolder = len(os.listdir(pathToFolder))
    return numberOfFilesInFolder == 0

def determineProjectName(absPathToGitRepository):
    if isEmptyFolder(absPathToGitRepository):
        print("\tWarning:", absPathToGitRepository, "is empty. If it is supposed to be a submodule, be sure to initialize it, or it will be reported as its containing project instead of being reported individually.")
        #return None
    os.chdir(absPathToGitRepository)
    process = subprocess.run(["git", "rev-parse", "--show-toplevel"], stdout=PIPE, stderr=PIPE)
    lines = process.stdout.splitlines()
    if len(lines) == 1:
        pathToProjectRoot = lines[0].decode(SUBPROCESS_OUTPUT_ENCODING)
        splittablePath = pathlib.Path(pathToProjectRoot)
        pathParts = splittablePath.parts
        if len(pathParts) > 0:
            projectName = pathParts[len(pathParts) - 1]
            return projectName
    return None

def determineRepositoryUrl(absPathToGitRepository):
    os.chdir(absPathToGitRepository)
    process = subprocess.run(["git", "config", "--get", "remote.origin.url"], stdout=PIPE, stderr=PIPE)
    lines = process.stdout.splitlines()
    if len(lines) == 1:
        resultUrl = lines[0].decode(SUBPROCESS_OUTPUT_ENCODING)
        return resultUrl
    return None

def searchGitModulesFile(absolutePathToObject):
    pathToGitModulesFile = os.path.join(absolutePathToObject, FILE_NAME_OF_GITMODULES_FILE)
    if os.path.exists(pathToGitModulesFile):
        return pathToGitModulesFile
    return None

def getAssignmentRhs(line):
    parts = line.partition("=")
    rhs = parts[2].strip()
    return rhs

# Parses the given Git modules files and returns a list of GitSubModule objects. Each Git module in the file is
# represented by one GitSubModule object in the list.
def parseGitModulesFile(pathToGitModulesFile):
    submodulesFound = []
    gitModulesFile = open(pathToGitModulesFile)
    
    currentSubModule = GitSubModule()
    for line in gitModulesFile:
        line = line.strip()
        if line.startswith(LINE_PREFIX_SUBMODULE_SECTION_START):
            # Start of a new submodule means that the previous one should be complete, unless it is the first one in the file
            if currentSubModule.isComplete():
                submodulesFound.append(currentSubModule)
                currentSubModule = GitSubModule()
            elif len(submodulesFound) > 0:
                print("Warning: incomplete submodule description found in file:", pathToGitModulesFile, file = sys.stderr)
            
            # Start of a new submodule
            smNameTmp = line.split(LINE_PREFIX_SUBMODULE_SECTION_START)
            if len(smNameTmp) > 1:
                smName = smNameTmp[1]
                if smName.find(']') != -1:
                    smName = smName[:smName.find(']')]
                smName = smName.replace("\"", "")
                currentSubModule.name = smName
                    
        elif line.startswith(LINE_PREFIX_PATH):
            currentSubModule.path = getAssignmentRhs(line)
        elif line.startswith(LINE_PREFIX_URL):
            currentSubModule.url = getAssignmentRhs(line)
    
    if currentSubModule.isComplete():
        submodulesFound.append(currentSubModule)
    else:
        print("Warning: last submodule description is incomplete in file:", pathToGitModulesFile, file = sys.stderr)
    gitModulesFile.close()
    return submodulesFound

def insertProjectIntoDatabase(dbConnection, projectNameOfRepository, remoteUrlOfRepository):
    cursor = dbConnection.cursor()
    cursor.execute(queryForSourceCodeProjectByName, [projectNameOfRepository])
    idsForProject = set()
    urlsForProject = set()
    for dataRow in cursor:
        idsForProject.add(dataRow[0])
        urlsForProject.add(dataRow[2])
    if len(urlsForProject) > 1:
        print("Warning: multiple repository URLs found for project:", projectNameOfRepository)
    if len(idsForProject) == 0:
        cmdToExecute = sqlCmdForInsertingNewProject.format(quote(projectNameOfRepository), quote(remoteUrlOfRepository))
        cursor.execute(cmdToExecute)
        dbConnection.commit()
    elif len(idsForProject) == 1:
        # Possible improvement: check whether remoteUrlOfRepository is equal to the one found in the database
        pass
    elif len(idsForProject) > 1:
        raise Exception("Internal error: more than one database entry for " + projectNameOfRepository)
    else:
        raise Exception("Internal error: should not reach this. Problem caused by " + projectNameOfRepository)
    
def createDependencyEntryInDatabase(dbConnection, projectNameOfRepository, projectNameOfSubModule):
    print("\tStoring dependency:", projectNameOfRepository, " -> ", projectNameOfSubModule)
    cursor = dbConnection.cursor()
    cmdToExecute = sqlCmdForInsertingDependsOnRelation.format(quote(projectNameOfRepository), quote(projectNameOfSubModule))
    cursor.execute(cmdToExecute)
    dbConnection.commit()
    
def quote(stringToQuote):
    return "'" + stringToQuote + "'"

def analyzeGitRepository(absolutePathToObject, dbConnection, pathIsSubmoduleAndAllowedToBeMissing = False):
    print("Analyzing directory:", absolutePathToObject)
    if not os.path.exists(absolutePathToObject) and pathIsSubmoduleAndAllowedToBeMissing:
        print("Warning:", absolutePathToObject, " does not exist. It is supposed to be a submodule, probably it is not",
              "initialized. Will ignore this submodule and proceed.")
        return
    if not isGitRepository(absolutePathToObject):
        return
    print("\tDirectory is a Git repository.")
    projectNameOfRepository = determineProjectName(absolutePathToObject)
    remoteUrlOfRepository = determineRepositoryUrl(absolutePathToObject)
    insertProjectIntoDatabase(dbConnection, projectNameOfRepository, remoteUrlOfRepository)
    print("\tScanning for submodules...")
    gitModulesFile = searchGitModulesFile(absolutePathToObject)
    if gitModulesFile != None:
        submodules = parseGitModulesFile(gitModulesFile)
        print("\tFound", len(submodules), "submodule(s)")
        for currentSubModule in submodules:
            absPathToSubModule = os.path.join(absolutePathToObject, currentSubModule.path)
            projectNameOfSubModule = currentSubModule.getProjectNameFromUrl()
            insertProjectIntoDatabase(dbConnection, projectNameOfSubModule, currentSubModule.url)
            createDependencyEntryInDatabase(dbConnection, projectNameOfRepository, projectNameOfSubModule)
            analyzeGitRepository(absPathToSubModule, dbConnection, True)
    else:
        print("\tDone:", absolutePathToObject, "does not have any submodules")

def connectToDatabase():
    if not os.path.exists(DATABASE_FILE_NAME):
        raise FileNotFoundError("Database file not found: " + DATABASE_FILE_NAME)
    return sqlite3.connect(DATABASE_FILE_NAME)

def processCmdLineArguments(args):
    dbConnection = connectToDatabase()
    absolutePathToObject = os.path.abspath(args.directory)
    if os.path.exists(absolutePathToObject):
        if os.path.isdir(absolutePathToObject):
            if args.allDirectoriesInPath:
                analyzeRepositoryRootDir(absolutePathToObject, dbConnection)
            else:
                analyzeGitRepository(absolutePathToObject, dbConnection)
        else:
            dbConnection.close()
            raise NotADirectoryError("The argument is not a directory")
    else:
        dbConnection.close()
        raise FileNotFoundError("Not found in file system: " + absolutePathToObject)
    dbConnection.close()

def main():
    argumentParser = createArgumentParser()
    args = argumentParser.parse_args()
    prepareSqlStatements()
    try:
        processCmdLineArguments(args)
    except (NotADirectoryError, FileNotFoundError) as e:
        print("Error:", e, file = sys.stderr)
        sys.exit(1)


## Main ##
main()
