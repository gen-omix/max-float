from max_float import config


def test_every_river_has_a_season_section_gauge_and_flows():
    tables = (
        config.SEASONS,
        config.SECTIONS,
        config.LOTTERY_RULES,
        config.GAUGES,
        config.FLOWS,
    )
    for table in tables:
        assert set(table) == set(config.RIVERS)


def test_rules_have_the_same_fields():
    assert len({tuple(rules) for rules in config.LOTTERY_RULES.values()}) == 1


def test_every_river_has_a_max_trip_length():
    assert all(rules["max_trip_days"] for rules in config.LOTTERY_RULES.values())


def test_rivers_in_one_lottery_share_its_choices():
    choices = {}
    for river, ridb_id in config.RIVERS.items():
        count = config.LOTTERY_RULES[river]["choices_per_application"]
        assert choices.setdefault(ridb_id, count) == count


def test_each_flow_category_after_the_first_has_a_rising_start():
    for starts in config.FLOWS.values():
        assert len(starts) == len(config.FLOW_CATEGORIES) - 1
        assert list(starts) == sorted(set(starts))


def test_text_is_ascii():
    assert all(section.isascii() for section in config.SECTIONS.values())
    assert all(category.isascii() for category in config.FLOW_CATEGORIES)


def test_each_temperature_category_after_the_first_has_a_rising_start():
    starts = config.TEMPERATURE_STARTS
    assert len(starts) == len(config.TEMPERATURE_CATEGORIES) - 1
    assert list(starts) == sorted(set(starts))
