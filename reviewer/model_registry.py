from dataclasses import dataclass


@dataclass(frozen=True)
class AIModel:
    key: str
    ollama_name: str
    display_name: str
    description: str


AI_MODELS = {
    "qwen": AIModel(
        key="qwen",
        ollama_name="qwen2.5-coder:3b",
        display_name="Qwen2.5-Coder 3B",
        description=(
            "Основная модель проекта. "
            "Специализирована на анализе и генерации кода."
        ),
    ),
    "deepseek": AIModel(
        key="deepseek",
        ollama_name="deepseek-coder:1.3b-instruct",
        display_name="DeepSeek Coder 1.3B",
        description=(
            "Легковесная модель для работы с программным кодом. "
            "Используется для сравнения с Qwen."
        ),
    ),
}


DEFAULT_MODEL_KEY = "qwen"


def get_model(
    model_key: str,
) -> AIModel:
    model = AI_MODELS.get(model_key)

    if model is None:
        available_models = ", ".join(AI_MODELS)

        raise ValueError(
            f"Неизвестная модель: {model_key}. "
            f"Доступные модели: {available_models}."
        )

    return model


def get_all_models() -> list[AIModel]:
    return list(AI_MODELS.values())


def get_model_options() -> dict[str, str]:
    """
    Возвращает значения для элементов интерфейса:

    {
        "qwen": "Qwen2.5-Coder 3B",
        "deepseek": "DeepSeek Coder 1.3B",
    }
    """

    return {
        model.key: model.display_name
        for model in get_all_models()
    }