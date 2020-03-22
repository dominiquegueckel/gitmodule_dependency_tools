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
import sqlite3
import sys

DATABASE_FILE_NAME = "gitproject_dependency_database.db"

# Paths to Data Definition Language (DDL) files. These are required for creating tables.
PATH_TO_DDL_FOR_TABLE_SOURCE_CODE_PROJECT = "ddl/tableSourceCodeProject.sql"
PATH_TO_DDL_FOR_TABLE_DEPENDS_ON = "ddl/tableDependsOn.sql"
PATH_TO_DDL_FOR_TABLE_JENKINS_BUILD_JOBS = "ddl/tableJenkinsBuildJob.sql"
PATH_TO_DDL_FOR_TABLE_BUILDS = "ddl/tableBuilds.sql"

def createTableFromDdlFile(pathToDdlFile, dbCursor):
    sqlCommand = ""
    ddlFile = open(pathToDdlFile)
    for line in ddlFile:
        sqlCommand += line
    ddlFile.close()
    dbCursor.execute(sqlCommand)

def createDatabase():
    connection = sqlite3.connect(DATABASE_FILE_NAME)
    cursor = connection.cursor()
    createTableFromDdlFile(PATH_TO_DDL_FOR_TABLE_SOURCE_CODE_PROJECT, cursor)
    createTableFromDdlFile(PATH_TO_DDL_FOR_TABLE_JENKINS_BUILD_JOBS, cursor)
    createTableFromDdlFile(PATH_TO_DDL_FOR_TABLE_DEPENDS_ON, cursor)
    createTableFromDdlFile(PATH_TO_DDL_FOR_TABLE_BUILDS, cursor)
    connection.commit()
    connection.close()

def main():
    if os.path.exists(DATABASE_FILE_NAME):
        os.remove(DATABASE_FILE_NAME)
        #print("Error: database file already exists. Will not touch it", file = sys.stderr)
        #sys.exit(1)
    createDatabase()

## Main ##
main()
