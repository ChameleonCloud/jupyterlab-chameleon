class AuthenticationError(Exception):
    pass

class BadRequestError(Exception):
    pass

class IllegalArchiveError(Exception):
    pass

class ArtifactNotFoundError(Exception):
    pass

class DuplicateArtifactError(Exception):
    pass
