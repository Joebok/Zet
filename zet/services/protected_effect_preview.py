"""State-bound approval conflicts for bulk image actions."""


class ProtectedEffectsChanged(ValueError):
    def __init__(self, preview: dict):
        super().__init__("Image state changed; review the affected images again.")
        self.preview = preview
