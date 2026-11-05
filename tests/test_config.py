from max_float import config


def test_every_river_has_a_season_section_gauge_and_flows():
    for table in (config.SEASONS, config.SECTIONS, config.GAUGES, config.FLOWS):
        assert set(table) == set(config.RIVERS)


def test_each_flow_category_after_the_first_has_a_rising_start():
    for starts in config.FLOWS.values():
        assert len(starts) == len(config.FLOW_CATEGORIES) - 1
        assert list(starts) == sorted(set(starts))


def test_text_is_ascii():
    assert all(section.isascii() for section in config.SECTIONS.values())
    assert all(category.isascii() for category in config.FLOW_CATEGORIES)
