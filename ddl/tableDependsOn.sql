CREATE TABLE DependsOn (
    firstProject INTEGER,
    secondProject INTEGER,
    PRIMARY KEY (firstProject, secondProject),
    FOREIGN KEY(firstProject) REFERENCES SourceCodeProject(id),
    FOREIGN KEY(secondProject) REFERENCES SourceCodeProject(id)
)
