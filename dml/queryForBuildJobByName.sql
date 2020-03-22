SELECT id, buildJobName, sourceCodeRepositoryUrl
FROM JenkinsBuildJob
WHERE buildJobName = ?
