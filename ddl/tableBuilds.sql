CREATE TABLE Builds(
    buildJobId INTEGER,
    sourceProjectId INTEGER,
    PRIMARY KEY (buildJobId, sourceProjectId),
    FOREIGN KEY(buildJobId) REFERENCES JenkinsBuildJob(id),
    FOREIGN KEY(sourceProjectId) REFERENCES SourceCodeProject(id)
)
