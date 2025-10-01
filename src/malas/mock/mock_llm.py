# auto_fake_llm.py

from crewai import BaseLLM
from pydantic import BaseModel
from typing import Any, Dict, List, Union

import re
from malas.mock.dummy_factory import create_dummy_instance

def parse_context_from_description(description: str) -> Dict[str, str]:
    """
    Fungsi helper untuk mengekstrak variabel dari deskripsi task
    menggunakan pola spesifik.
    """
    context = {}
    
    # Pola Regex untuk mengekstrak nilai dari 'bab : {bab_now}'
    # Ia akan menangkap semua teks di antara "bab : " dan " dengan subab"
    bab_match = re.search(r"bab : (.*?) dengan subab", description)
    
    # Pola Regex untuk mengekstrak nilai dari 'subab : {subbab_now}'
    # Ia akan menangkap semua teks di antara "subab : " dan " menyesuaikan"
    subbab_match = re.search(r"subab : (.*?) menyesuaikan", description)

    if bab_match:
        # group(1) mengambil teks yang ada di dalam kurung (...) pertama
        context['bab_now'] = bab_match.group(1).strip()
        
    if subbab_match:
        context['subbab_now'] = subbab_match.group(1).strip()
        
    return context

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
        task_context = parse_context_from_description(task.description)
        
        # Panggil pabrik untuk membuat instance dummy secara on-the-fly
        dummy_instance = create_dummy_instance(expected_model_class,context=task_context)
        
        return dummy_instance.model_dump_json(indent=2)

    def supports_function_calling(self) -> bool:
        return False