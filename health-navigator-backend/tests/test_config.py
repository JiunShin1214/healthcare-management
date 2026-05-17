import importlib


def reload_config(monkeypatch, **env):
    keys = {
        "SYMPTOM_STRUCTURE_PROVIDER_ENABLED",
        "SYMPTOM_STRUCTURE_PROVIDER_NAME",
        "SYMPTOM_STRUCTURE_MODEL_ID",
        "SYMPTOM_STRUCTURE_TIMEOUT_MS",
        "CLOVA_OCR_INVOKE_URL",
        "CLOVA_OCR_SECRET_KEY",
    }
    for key in keys:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("CLOVA_OCR_INVOKE_URL", "https://example.test/ocr")
    monkeypatch.setenv("CLOVA_OCR_SECRET_KEY", "test-secret")
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    import app.core.config as config

    return importlib.reload(config)


def test_symptom_structure_provider_config_defaults_to_disabled(monkeypatch):
    config = reload_config(monkeypatch)

    assert config.SYMPTOM_STRUCTURE_PROVIDER_ENABLED is False
    assert config.SYMPTOM_STRUCTURE_PROVIDER_NAME == "none"
    assert config.SYMPTOM_STRUCTURE_MODEL_ID == ""
    assert config.SYMPTOM_STRUCTURE_TIMEOUT_MS == 2000


def test_symptom_structure_provider_config_reads_non_secret_env(monkeypatch):
    config = reload_config(
        monkeypatch,
        SYMPTOM_STRUCTURE_PROVIDER_ENABLED="true",
        SYMPTOM_STRUCTURE_PROVIDER_NAME="openai",
        SYMPTOM_STRUCTURE_MODEL_ID="configured-model",
        SYMPTOM_STRUCTURE_TIMEOUT_MS="1500",
    )

    assert config.SYMPTOM_STRUCTURE_PROVIDER_ENABLED is True
    assert config.SYMPTOM_STRUCTURE_PROVIDER_NAME == "openai"
    assert config.SYMPTOM_STRUCTURE_MODEL_ID == "configured-model"
    assert config.SYMPTOM_STRUCTURE_TIMEOUT_MS == 1500


def test_symptom_structure_provider_timeout_falls_back_to_default(monkeypatch):
    config = reload_config(monkeypatch, SYMPTOM_STRUCTURE_TIMEOUT_MS="not-an-int")

    assert config.SYMPTOM_STRUCTURE_TIMEOUT_MS == 2000
