# core/tcl_multi_model.py

from Ladruno.multiple_file.run_all import RecursiveModelRunner

class TCL_MultiModel:
    def __init__(self,
                 model_path: str,
                 number_of_nodes: int = 1,
                 max_nodes: int = 18,
                 max_tasks_per_node: int = 32,
                 verbose: bool = False,
                 opensees_exe='/mnt/nfshare/bin/openseesmp-26062025'):
        """
        Clase para manejar múltiples modelos TCL en subcarpetas.
        """
        self.model_path = model_path

        self.run = RecursiveModelRunner(
            base_path=model_path,
            number_of_nodes=number_of_nodes,
            max_nodes=max_nodes,
            max_tasks_per_node=max_tasks_per_node,
            verbose=verbose,
            opensees_exe=opensees_exe
        )

    def submit(self, **kwargs):
        """
        Ejecuta todos los modelos encontrados recursivamente.
        """
        self.run.submit_all(**kwargs)
