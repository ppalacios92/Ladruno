# core/model.py

from pathlib import Path
from Ladruno.engine.run import Run

class Model:
    def __init__(self,
                 path: str,
                 number_of_nodes: int = 1,
                 max_nodes: int = 18,
                 max_tasks_per_node: int = 32,
                 verbose: bool = False,
                 opensees_exe: str = "/mnt/nfshare/bin/openseesmp-26062025",
                 archive_destination: str = "/mnt/krakenschest/home/pxpalacios"):
        
        self.path = Path(path).resolve()
        self.number_of_nodes = number_of_nodes
        self.max_nodes = max_nodes
        self.max_tasks_per_node = max_tasks_per_node
        self.verbose = verbose
        self.opensees_exe = opensees_exe
        self.archive_destination = archive_destination
        
        self.runs = self._collect_runs()
        
        if not self.runs:
            raise FileNotFoundError(f"No main.tcl found in: {self.path}")
    
    def _collect_runs(self):
        if (self.path / "main.tcl").exists():
            return [self._create_run(self.path)]
        
        runs = []
        for tcl_path in sorted(self.path.rglob("main.tcl")):
            runs.append(self._create_run(tcl_path.parent))
        return runs
    
    def _create_run(self, folder_path):
        return Run(
            folder_path=str(folder_path),
            number_of_nodes=self.number_of_nodes,
            max_nodes=self.max_nodes,
            max_tasks_per_node=self.max_tasks_per_node,
            verbose=self.verbose,
            opensees_exe=self.opensees_exe,
            archive_destination=self.archive_destination
        )
    
    def submit(self,
               archive: bool = False,
               fix: bool = True,
               rebuild: bool = True,
               job_name: str | None = None,
               nodes: int | None = None,
               ntasks: int | None = None,
               ntasks_per_node: int | None = None,
               exclude: list[str] | None = None,
               tcl_file: str = "main.tcl",
               monitor_ram: bool = False,
               monitor_interval: int = 30,
               log_file: str = "memtrack_node.txt"):
        
        job_ids = []
        total = len(self.runs)
        
        if self.verbose:
            print(f"\n🚀 Submitting {total} model(s)\n")
        
        for i, run in enumerate(self.runs, start=1):
            if self.verbose:
                print(f"[{i}/{total}] {run.path.name}")
            
            job_id = run.submit(
                archive=archive,
                fix=fix,
                rebuild=rebuild,
                job_name=job_name,
                nodes=nodes,
                ntasks=ntasks,
                ntasks_per_node=ntasks_per_node,
                exclude=exclude,
                tcl_file=tcl_file,
                monitor_ram=monitor_ram,
                monitor_interval=monitor_interval,
                log_file=log_file
            )
            job_ids.append(job_id)
        
        if self.verbose:
            print(f"\n✅ {total} job(s) submitted")
            print("LARGA VIDA AL LADRUÑO!!!\n")
        
        return job_ids