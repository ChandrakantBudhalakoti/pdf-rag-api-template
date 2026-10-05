import pytest

from rag_pipeline.config import DEFAULTS, ConfigError, Settings, validate_chunk_params


def make(**overrides) -> Settings:
    env = {"OPENAI_API_KEY": "sk-test-not-real", **overrides}
    return Settings.from_env(env=env)


def test_defaults_match_env_example():
    s = make()
    assert s.chunk_size == 1000
    assert s.chunk_overlap == 200
    assert s.embedding_model == "text-embedding-3-small"
    assert s.llm_model == "gpt-4o-mini"
    assert s.database_url == DEFAULTS["DATABASE_URL"]
    assert s.pdf_dir.name == "pdfs"


def test_values_are_read_from_env():
    s = make(CHUNK_SIZE="500", CHUNK_OVERLAP="50", EMBEDDING_MODEL="text-embedding-3-large",
             LLM_MODEL="gpt-4o", TOP_K="6", COLLECTION_NAME="other")
    assert (s.chunk_size, s.chunk_overlap, s.top_k) == (500, 50, 6)
    # embedding and chat models are configured independently
    assert s.embedding_model == "text-embedding-3-large"
    assert s.llm_model == "gpt-4o"
    assert s.collection_name == "other"


@pytest.mark.parametrize("size,overlap", [(0, 0), (-5, 0), (100, -1), (100, 100), (100, 150)])
def test_invalid_chunk_params_rejected(size, overlap):
    with pytest.raises(ConfigError):
        validate_chunk_params(size, overlap)
    with pytest.raises(ConfigError):
        make(CHUNK_SIZE=str(size), CHUNK_OVERLAP=str(overlap))


def test_valid_chunk_params_accepted():
    validate_chunk_params(100, 0)
    validate_chunk_params(100, 99)


@pytest.mark.parametrize("name", ["CHUNK_SIZE", "CHUNK_OVERLAP", "TOP_K"])
def test_non_integer_values_rejected(name):
    with pytest.raises(ConfigError, match=name):
        make(**{name: "abc"})


def test_top_k_must_be_positive():
    with pytest.raises(ConfigError, match="TOP_K"):
        make(TOP_K="0")


def test_non_postgres_database_url_rejected():
    with pytest.raises(ConfigError, match="PostgreSQL"):
        make(DATABASE_URL="sqlite:///x.db")


def test_missing_api_key_gives_clear_error():
    s = Settings.from_env(env={})
    assert not s.has_api_key
    with pytest.raises(ConfigError, match="OPENAI_API_KEY"):
        s.require_api_key()


def test_openai_is_the_default_provider():
    assert make().provider == "openai"


def test_gemini_provider_uses_gemini_defaults_and_key():
    s = Settings.from_env(env={"AI_PROVIDER": "Gemini", "GOOGLE_API_KEY": "g-test"})
    assert s.provider == "gemini"
    assert s.embedding_model == "gemini-embedding-001"
    assert s.llm_model == "gemini-2.5-flash"
    assert s.api_key == "g-test"
    s.require_api_key()


def test_gemini_api_key_alias_accepted():
    assert Settings.from_env(env={"AI_PROVIDER": "gemini", "GEMINI_API_KEY": "g2"}).api_key == "g2"


def test_gemini_without_key_names_google_key():
    s = Settings.from_env(env={"AI_PROVIDER": "gemini", "OPENAI_API_KEY": "sk-x"})
    with pytest.raises(ConfigError, match="GOOGLE_API_KEY"):
        s.require_api_key()


@pytest.mark.parametrize("provider,var,model", [
    ("gemini", "EMBEDDING_MODEL", "text-embedding-3-small"),
    ("gemini", "LLM_MODEL", "gpt-4o-mini"),
    ("openai", "LLM_MODEL", "gemini-2.5-flash"),
])
def test_model_from_other_provider_rejected(provider, var, model):
    with pytest.raises(ConfigError, match=var):
        Settings.from_env(env={"AI_PROVIDER": provider, var: model})


def test_unknown_provider_rejected():
    with pytest.raises(ConfigError, match="AI_PROVIDER"):
        Settings.from_env(env={"AI_PROVIDER": "llama"})


def test_api_key_never_appears_in_repr():
    s = make(OPENAI_API_KEY="sk-super-secret-value", GOOGLE_API_KEY="g-super-secret-value")
    for secret in ("sk-super-secret-value", "g-super-secret-value"):
        assert secret not in repr(s)
        assert secret not in str(s)


def test_psycopg_url_strips_driver():
    assert make().psycopg_url.startswith("postgresql://")


def test_llm_requests_per_minute():
    assert make().llm_requests_per_minute == 0  # no limit by default
    assert make(LLM_REQUESTS_PER_MINUTE="5").llm_requests_per_minute == 5
    with pytest.raises(ConfigError, match="LLM_REQUESTS_PER_MINUTE"):
        make(LLM_REQUESTS_PER_MINUTE="-1")
