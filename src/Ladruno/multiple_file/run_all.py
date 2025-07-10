

import os
from Ladruno.core.tcl_model import TCL_Model

class RecursiveModelRunner:
    def __init__(self, base_path: str, **model_kwargs):
        """
        Ejecuta múltiples modelos TCL desde subcarpetas que contengan un main.tcl.
        """
        self.base_path = base_path
        self.model_kwargs = model_kwargs
        self.models = self._collect_models()

    def _collect_models(self):
        """
        Busca *recursivamente* todos los main.tcl y crea TCL_Model para cada uno.
        """
        models = []
        for root, _, files in os.walk(self.base_path):
            if "main.tcl" in files:
                models.append(TCL_Model(model_path=root, **self.model_kwargs))
        return models


    def submit_all(self, **submit_kwargs):
        """
        Envía todos los modelos usando run.submit() con prints detallados.
        """
        print("\n🚀 INICIANDO ENVÍO DE MODELOS RECURSIVOS\n")

        total_jobs = 0
        for i, model in enumerate(self.models, start=1):
            print(f"+{'-'*40}+")
            print(f"[{i:02d}] Enviando: {model.model_path}")
            try:
                job_id = model.run.submit(**submit_kwargs)
                print(f"✅ Job enviado correctamente → ID: {job_id}")
            except Exception as e:
                print(f"❌ ERROR al enviar el modelo: {e}")
            total_jobs += 1

        print(f"\n+{'='*40}+")
        print(f"📦 Total de modelos enviados: {total_jobs}")
        print(f"\n✅ All recursive jobs submitted successfully.")
        print("LARGA VIDA AL LADRUÑO!!! 🏴‍☠️\n")

