from zet.models.asset import Asset
from zet.services.asset_service import asset_sort_key


def test_asset_sorting_uses_pipeline_view_and_costume_or_expression() -> None:
    assets = [
        Asset(1, "Test", "Adult", "Character-Assembly", "Front"),
        Asset(2, "Test", "Adult", "Head-Image", "Front"),
        Asset(3, "Test", "Adult", "Body-Reference", "Left-Profile"),
        Asset(4, "Test", "Adult", "Body-Reference", "Front-Right-3-4"),
        Asset(5, "Test", "Adult", "Costume-Dressing", "Front", costume="Zulu"),
        Asset(6, "Test", "Adult", "Costume-Dressing", "Front", costume="Alpha"),
        Asset(7, "Test", "Adult", "Expression", "Front", costume="Alpha", expression="Sad"),
        Asset(8, "Test", "Adult", "Expression", "Front", costume="Zulu", expression="Happy"),
        Asset(9, "Test", "Adult", "Head-Fitment", "Front"),
    ]

    assert [asset.asset_id for asset in sorted(assets, key=asset_sort_key)] == [4, 3, 2, 9, 1, 6, 5, 8, 7]
