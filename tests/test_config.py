import app.config as config


def test_T_MAX():
    assert config.T_MAX == 12


def test_CIRCUITY_FLAG():
    assert config.CIRCUITY_FLAG == 1.4


def test_SOLVER_NUM_WORKERS():
    assert isinstance(config.SOLVER_NUM_WORKERS, int)
    # Default value from environment variable fallback
    assert config.SOLVER_NUM_WORKERS == 8
