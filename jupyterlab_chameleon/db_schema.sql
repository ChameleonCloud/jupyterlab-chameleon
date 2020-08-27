-- Artifacts: store a mapping of shared artifacts to their imported location
-- on the Notebook file system.
create table if not exists artifacts
  ([id] text, [path] text, [deposition_repo] text, [ownership] text)
