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
from xml.etree import ElementTree

SUBPROCESS_OUTPUT_ENCODING = 'utf-8'

DATABASE_FILE_NAME = "gitproject_dependency_database.db"
PATH_TO_DML_QUERY_FOR_BUILD_JOB_BY_NAME = "dml/queryForBuildJobByName.sql"
PATH_TO_DML_COMMAND_FOR_INSERTING_NEW_BUILD_JOB = "dml/cmdForInsertingNewBuildJob.sql"
#PATH_TO_DML_COMMAND_FOR_INSERTING_DEPENDS_ON_RELATION = "dml/cmdForInsertingDependsOnRelation.sql"

queryForBuildJobByName = ""
sqlCmdForInsertingNewBuildJob = ""

XPATH_FOR_GIT_URL = ".//source/remote"
XPATH_FOR_PROJECT_NAME = ".//displayName"

def createArgumentParser():
    parser = argparse.ArgumentParser(description="Scans Jenkins job descriptions given in the form of XML files and extracts the job name and URL of the Git repository. The results are written into an Sqlite database.")
    parser.add_argument("-d", "--directory", 
        dest = "directory",
        action = "store",
        help = "Scan the given directory for Jenkins job description files. Each file is then treated as if given as the argument for \"-f\".")
    parser.add_argument("-f", "--file",
        dest="file",
        action="store",
        help = "The file to examine")
    return parser

def prepareSqlStatementFromFile(pathToFile):
    statementFromFile = ""
    with open(pathToFile, 'r') as inputFile:
        statementFromFile = inputFile.read()
    statementFromFile = statementFromFile.replace("\n", " ")
    return statementFromFile

def prepareSqlStatements():
    global queryForBuildJobByName
    queryForBuildJobByName = prepareSqlStatementFromFile(PATH_TO_DML_QUERY_FOR_BUILD_JOB_BY_NAME)
    global sqlCmdForInsertingNewBuildJob 
    sqlCmdForInsertingNewBuildJob = prepareSqlStatementFromFile(PATH_TO_DML_COMMAND_FOR_INSERTING_NEW_BUILD_JOB)

def insertBuildJobIntoDatabase(dbConnection, projectName, remoteUrlOfRepository):
    cursor = dbConnection.cursor()
    cursor.execute(queryForBuildJobByName, [projectName])
    idsForProject = set()
    urlsForProject = set()
    for dataRow in cursor:
        idsForProject.add(dataRow[0])
        urlsForProject.add(dataRow[2])
    if len(urlsForProject) > 1:
        print("Warning: multiple repository URLs found for project:", projectName)
    if len(idsForProject) == 0:
        cmdToExecute = sqlCmdForInsertingNewBuildJob.format(quote(projectName), quote(remoteUrlOfRepository))
        cursor.execute(cmdToExecute)
        dbConnection.commit()
    elif len(idsForProject) == 1:
        # Possible improvement: check whether remoteUrlOfRepository is equal to the one found in the database
        print("OK:", projectName, "is already contained in the database. Nothing to do here.")
    elif len(idsForProject) > 1:
        raise ValueError("Internal error: more than one database entry for " + projectName)
    else:
        raise Exception("Internal error: should not reach this. Problem caused by " + projectName)
        
def quote(stringToQuote):
    return "'" + stringToQuote + "'"

def connectToDatabase():
    if not os.path.exists(DATABASE_FILE_NAME):
        raise FileNotFoundError("Database file not found: " + DATABASE_FILE_NAME)
    return sqlite3.connect(DATABASE_FILE_NAME)

# Examines the given XML file and searches for the project name and project source URL.
# Returns: project name, project source URL if both fields exist. (None, None) else.
def examineXmlFile(pathToXmlFile):
    absolutePathToObject = os.path.abspath(pathToXmlFile)
    if not os.path.exists(absolutePathToObject):
        raise FileNotFoundError("Not found in file system: " + absolutePathToObject)
    if os.path.isdir(absolutePathToObject):
        raise IsADirectoryError("The argument is a directory: " + absolutePathToObject)
    print("Examining XML file:", absolutePathToObject)
    xmlTree = ElementTree.parse(absolutePathToObject)
    root = xmlTree.getroot()
    projectNames = root.findall(XPATH_FOR_PROJECT_NAME)
    gitSourceUrls = root.findall(XPATH_FOR_GIT_URL)
    if projectNames != None and len(projectNames) == 1 and gitSourceUrls != None and len(gitSourceUrls) == 1:
        projectName = projectNames[0]
        gitSourceUrl = gitSourceUrls[0]
        return projectName.text, gitSourceUrl.text
    return None, None

def scanDirectoryForXmlFiles(pathToDirectory):
    absolutePathToObject = os.path.abspath(pathToDirectory)
    if not os.path.exists(absolutePathToObject):
        raise FileNotFoundError("Not found in file system: " + absolutePathToObject)
    if not os.path.isdir(absolutePathToObject):
        raise NotADirectoryError("The argument is not a directory: " + absolutePathToObject)
    xmlFiles = []
    for filename in os.listdir(absolutePathToObject):
        pathToFile = os.path.join(absolutePathToObject, filename)
        absolutePathToFile = os.path.abspath(pathToFile)
        if os.path.isfile(absolutePathToFile) and absolutePathToFile.lower().endswith(".xml"):
            xmlFiles.append(absolutePathToFile)
    return xmlFiles

def processXmlJobDescription(dbConnection, pathToXmlFile):
    projectName, gitSourceUrl = examineXmlFile(pathToXmlFile)
    if projectName == None or gitSourceUrl == None:
        print("File", pathToXmlFile, "is not a valid description of a Jenkins job, skipping it.")
        return
    try:
        insertBuildJobIntoDatabase(dbConnection, projectName, gitSourceUrl)
    except ValueError as e:
        print("Error: cannot process", projectName, ". This project will be skipped. Detailed reason:", e, file = sys.stderr)

def processCmdLineArguments(args):
    assertArgumentConsistency(args)
    dbConnection = connectToDatabase()
    if args.file != None:
        processXmlJobDescription(dbConnection, args.file)
    if args.directory != None:
        xmlFiles = scanDirectoryForXmlFiles(args.directory)
        for xmlFile in xmlFiles:
            processXmlJobDescription(dbConnection, xmlFile)
    dbConnection.close()
    
def assertArgumentConsistency(args):
    checkFile = args.file != None
    checkDirectory = args.directory != None
    if not (checkFile ^ checkDirectory):
        raise ValueError("Incorrect arguments. Either --file or --directory must be set.")

def main():
    argumentParser = createArgumentParser()
    args = argumentParser.parse_args()
    prepareSqlStatements()
    try:
        processCmdLineArguments(args)
    except (NotADirectoryError, IsADirectoryError, FileNotFoundError, ValueError) as e:
        print("Error:", e, file = sys.stderr)
        sys.exit(1)


## Main ##
main()
