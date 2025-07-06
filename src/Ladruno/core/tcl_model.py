from Ladruno.single_file.run import Run

class TCL_Model:
    
    def __init__(self,
                 model_path: str,
                 number_of_nodes: int = 1, 
                 max_nodes: int = 18,
                 max_tasks_per_node: int = 32,
                 verbose: bool = False,
                 opensees_exe = '/mnt/nfshare/bin/openseesmp-26062025'):
        
        self.model_path = model_path
        
        # Composite classes
        self.run = Run(folder_path=model_path,
                       number_of_nodes=number_of_nodes,
                       max_nodes=max_nodes,
                       max_tasks_per_node=max_tasks_per_node,
                       verbose=verbose,
                       opensees_exe=opensees_exe)