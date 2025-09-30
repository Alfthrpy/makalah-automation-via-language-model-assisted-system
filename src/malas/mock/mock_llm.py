# auto_fake_llm.py

from crewai import BaseLLM
from pydantic import BaseModel
from typing import Any, Dict, List, Union
from malas.mock.dummy_factory import create_dummy_instance

class AutoFakeLLM(BaseLLM):
    """
    An auto-generating fake LLM. It dynamically creates a dummy Pydantic
    instance using a factory based on the task's expected output model.
    """
    def __init__(self, model_name: str):
        super().__init__(model=model_name, temperature=0.1)

    def call(
        self,
        messages: Union[str, List[Dict[str, str]]],
        **kwargs: Any,
    ) -> str:
        """
        Dynamically generates a dummy Pydantic object based on the task context.
        """
        task = kwargs.get('from_task')
        if not task or not task.output_pydantic:
            raise ValueError("AutoFakeLLM requires the task to have 'output_pydantic' set.")

        expected_model_class = task.output_pydantic
        
        # Panggil pabrik untuk membuat instance dummy secara on-the-fly
        dummy_instance = create_dummy_instance(expected_model_class)
        
        return dummy_instance.model_dump_json(indent=2)

    def supports_function_calling(self) -> bool:
        return False