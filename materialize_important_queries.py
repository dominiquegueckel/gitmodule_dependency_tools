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
import sqlite3

SUBPROCESS_OUTPUT_ENCODING = 'utf-8'

DATABASE_FILE_NAME = "gitproject_dependency_database.db"

sqlCmdForCleaningBuildsTable = "DELETE FROM Builds"
sqlCmdForFillingBuildsTable = "insert or replace into Builds (buildJobId, sourceProjectId) select b.id, s.id from SourceCodeProject s, JenkinsBuildJob b where s.SourceCodeRepositoryName = b.sourceCodeRepositoryUrl;"

def materializeBuildsRelation(dbConnection):
    cursor = dbConnection.cursor()
    cursor.execute(sqlCmdForCleaningBuildsTable)
    cursor.execute(sqlCmdForFillingBuildsTable)
    dbConnection.commit()

def connectToDatabase():
    if not os.path.exists(DATABASE_FILE_NAME):
        raise FileNotFoundError("Database file not found: " + DATABASE_FILE_NAME)
    return sqlite3.connect(DATABASE_FILE_NAME)

def materializeQueries():
    dbConnection = connectToDatabase()
    materializeBuildsRelation(dbConnection)
    dbConnection.close()

def main():
    try:
        materializeQueries()
    except FileNotFoundError as e:
        print("Error:", e, file = sys.stderr)
        sys.exit(1)


## Main ##
main()
