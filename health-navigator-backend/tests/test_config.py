import importlib


def reload_config(monkeypatch, **env):
    keys = {
        "SYMPTOM_STRUCTURE_PROVIDER_ENABLED",
        "SYMPTOM_STRUCTURE_PROVIDER_NAME",
        "SYMPTOM_STRUCTURE_MODEL_ID",
        "SYMPTOM_STRUCTURE_TIMEOUT_MS",
        "GEMINI_EXPLANATION_ENABLED",
        "GEMINI_EXPLANATION_MODEL_ID",
        "GEMINI_EXPLANATION_TIMEOUT_MS",
        "GEMINI_MODEL",
        "GCP_PROJECT_ID",
        "VERTEX_AI_LOCATION",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_CLOUD_LOCATION",
        "HEALTH_NAVIGATOR_SKIP_DOTENV",
        "CLOVA_OCR_INVOKE_URL",
        "CLOVA_OCR_SECRET_KEY",
    }
    for key in keys:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("CLOVA_OCR_INVOKE_URL", "https://example.test/ocr")
    monkeypatch.setenv("CLOVA_OCR_SECRET_KEY", "test-secret")
    monkeypatch.setenv("HEALTH_NAVIGATOR_SKIP_DOTENV", "true")
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
    assert config.GEMINI_EXPLANATION_ENABLED is False
    assert config.GOOGLE_APPLICATION_CREDENTIALS == ""
    assert config.GCP_PROJECT_ID == "health-navigator-497202"
    assert config.VERTEX_AI_LOCATION == "us-central1"
    assert config.GEMINI_MODEL == "gemini-2.5-flash"
    assert config.GEMINI_EXPLANATION_MODEL_ID == "gemini-2.5-flash"
    assert config.GEMINI_EXPLANATION_TIMEOUT_MS == 5000


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


def test_gemini_explanation_config_reads_env(monkeypatch):
    config = reload_config(
        monkeypatch,
        GEMINI_EXPLANATION_ENABLED="true",
        GOOGLE_APPLICATION_CREDENTIALS="C:/secrets/service-account.json",
        GCP_PROJECT_ID="vertex-project",
        VERTEX_AI_LOCATION="us-central1",
        GEMINI_MODEL="gemini-test",
        GEMINI_EXPLANATION_MODEL_ID="gemini-test",
        GEMINI_EXPLANATION_TIMEOUT_MS="2500",
    )

    assert config.GEMINI_EXPLANATION_ENABLED is True
    assert config.GOOGLE_APPLICATION_CREDENTIALS == "C:/secrets/service-account.json"
    assert config.GCP_PROJECT_ID == "vertex-project"
    assert config.VERTEX_AI_LOCATION == "us-central1"
    assert config.GEMINI_MODEL == "gemini-test"
    assert config.GEMINI_EXPLANATION_MODEL_ID == "gemini-test"
    assert config.GEMINI_EXPLANATION_TIMEOUT_MS == 2500
