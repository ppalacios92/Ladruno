# engine/run.py

from pathlib import Path
import re
import subprocess
import textwrap
from Ladruno.utilities.h5 import H5RepairTool

class Run:
    def __init__(self,
                 folder_path: str,
                 number_of_nodes: int = 1,
                 max_nodes: int = 18,
                 max_tasks_per_node: int = 32,
                 verbose: bool = False,
                 opensees_exe: str = "/mnt/nfshare/bin/openseesmp-26062025",
                 archive_destination: str = "/mnt/krakenschest/home/pxpalacios"):
        
        self.path = Path(folder_path).resolve()
        self.number_of_nodes = number_of_nodes
        self.max_nodes = max_nodes
        self.max_tasks_per_node = max_tasks_per_node
        self.verbose = verbose
        self.opensees_exe = Path(opensees_exe)
        self.archive_destination = Path(archive_destination)
        
        self.fix = H5RepairTool(
            directory=self.path,
            pattern="*.mpco",
            verbose=self.verbose
        )
        
        if not (self.path / "main.tcl").exists():
            raise FileNotFoundError(f"main.tcl not found in: {self.path}")
    
    def get_folder_name(self):
        return self.path.name
    
    def get_tasks(self):
        part_rx = re.compile(r"\.part-(\d+)\.mpco\.cdata$")
        indices = {
            int(m.group(1))
            for p in self.path.glob("**/*.mpco.cdata")
            if (m := part_rx.search(p.name))
        }
        
        if not indices:
            return 1
        
        max_idx = max(indices) + 1
        unique = len(indices)
        
        if self.verbose:
            print('----'*60)
            print(f"Found {unique} partitions, max index {max_idx - 1}")
        
        return max(max_idx, unique)
    
    def get_nodes_and_tasks(self):
        ntasks_required = max(self.get_tasks(), 1)
        tpn = max(self.max_tasks_per_node, 1)
        min_nodes = (ntasks_required + tpn - 1) // tpn
        nodes = max(min_nodes, self.number_of_nodes)
        
        if nodes > self.max_nodes:
            if self.verbose:
                print(f"⚠️ Capping nodes to {self.max_nodes}")
            nodes = self.max_nodes
        
        if nodes * tpn < ntasks_required:
            raise ValueError(f"Cannot fit {ntasks_required} tasks in {nodes} nodes × {tpn} tasks/node")
        
        if self.verbose:
            print(f"📦 nodes={nodes}, ntasks={ntasks_required}")
        
        return nodes, ntasks_required
    
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
        
        if rebuild:
            self.build_run_script(
                job_name=job_name,
                nodes=nodes,
                ntasks=ntasks,
                ntasks_per_node=ntasks_per_node,
                exclude=exclude,
                exe=self.opensees_exe,
                tcl_file=tcl_file,
                monitor_ram=monitor_ram,
                monitor_interval=monitor_interval,
                log_file=log_file,
                archive=archive
            )
        
        script = self.path / "run.sh"
        
        proc = subprocess.run(
            ["sbatch", str(script)],
            capture_output=True,
            text=True,
            check=True,
            cwd=self.path
        )
        
        job_id = int(proc.stdout.split()[-1])
        
        if self.verbose:
            print(f"🚀 Job {job_id} submitted")
        
        return job_id
    
    def _ram_monitor_block(self, interval: int = 30, log_file: str = "memtrack_node.txt"):
        return textwrap.dedent(f"""\
            ( while true; do
                printf '%s\\n' "$(date '+%F %T')" >> {log_file}
                free -h >> {log_file}
                echo "-----------" >> {log_file}
                pgrep -af openseesmp | while read PID CMD; do
                    echo "PID: $PID" >> {log_file}
                    ps -p "$PID" -o pid,%mem,rss,vsz,cmd --no-headers >> {log_file}
                done
                echo "======================" >> {log_file}
                sleep {interval}
            done & )
            MONITOR_PID=$!
        """)
    def _move_and_cleanup_block(self):
        return textwrap.dedent("""\
            EXIT_CODE=$?
            DURATION=$SECONDS
            
            # Forzar EXIT_CODE=0 si hay SUCCESS en el log
            if grep -q "SUCCESS" log.log 2>/dev/null; then
                EXIT_CODE=0
            fi
            
            echo "Elapsed: $DURATION seconds."
            echo "Code finished with exit code $EXIT_CODE."
            
            ORIG_PATH=$(pwd)
            REL_PATH="${ORIG_PATH#/mnt/deadmanschest/pxpalacios/}"
            DEST_BASE="/mnt/krakenschest/home/pxpalacios"
            DEST_PATH="${DEST_BASE}/${REL_PATH}"
            
            STATUS_FILE="status.txt"
            {
                echo "Execution Date: $(date)"
                echo "Executed By: $(whoami)"
                echo "Duration: $DURATION seconds"
                echo "Exit Code: $EXIT_CODE"
                echo "Original Path: $ORIG_PATH"
                echo "Destination Path: $DEST_PATH"
            } > "$STATUS_FILE"
            
            if [ "$EXIT_CODE" -eq 0 ]; then
                echo "📁 Copiando a destino: $DEST_PATH"
                mkdir -p "$DEST_PATH"
                rsync -a --exclude="status.txt" ./ "$DEST_PATH/"
                if [ $? -eq 0 ]; then
                    echo "✅ Copia completada. Limpiando carpeta original (excepto status.txt)..."
                    find . -mindepth 1 ! -name "status.txt" -exec rm -rf {} +
                    echo "🧼 Limpieza completa."
                else
                    echo "⚠️ Error en la copia. No se elimina nada."
                fi
            else
                echo "❌ Simulación fallida. No se copia ni borra nada."
            fi
            
            echo "LARGA VIDA AL LADRUÑO!!!"
        """)
    
    def build_run_script(self,
                        job_name: str | None = None,
                        nodes: int | None = None,
                        ntasks: int | None = None,
                        ntasks_per_node: int | None = None,
                        exclude: list[str] | None = None,
                        exe: str | Path = None,
                        tcl_file: str = "main.tcl",
                        monitor_ram: bool = False,
                        monitor_interval: int = 30,
                        log_file: str = "memtrack_node.txt",
                        archive: bool = False,
                        script_name: str = "run.sh"):
        
        if nodes is None or ntasks is None:
            nodes, ntasks = self.get_nodes_and_tasks()
        
        if ntasks_per_node is None:
            ntasks_per_node_cal = (ntasks + nodes - 1) // nodes
        else:
            ntasks_per_node_cal = ntasks_per_node
        
        if exe is None:
            exe = self.opensees_exe
        
        job_name = job_name or self.get_folder_name()
        
        header = [
            "#!/bin/bash",
            f"#SBATCH --job-name={job_name}",
            f"#SBATCH --output=log.log",
        ]
        
        if ntasks_per_node is not None:
            header.append(f"#SBATCH --ntasks-per-node={ntasks_per_node_cal}")
        else:
            header.append(f"#SBATCH --nodes={nodes}")
            header.append(f"#SBATCH --ntasks={ntasks}")
        
        if exclude:
            header.append(f"#SBATCH --exclude={','.join(exclude)}")
        
        monitor_block = self._ram_monitor_block(interval=monitor_interval, log_file=log_file) if monitor_ram else ""
        
        if archive:
            body = textwrap.dedent(f"""\
pwd; hostname; date
export OMP_NUM_THREADS=1
LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/mnt/nfshare/lib

{monitor_block}
SECONDS=0
mpirun {exe} {tcl_file}

[ -n "$MONITOR_PID" ] && kill "$MONITOR_PID" 2>/dev/null

{self._move_and_cleanup_block()}
""")
        else:
            body = textwrap.dedent(f"""\
pwd; hostname; date
export OMP_NUM_THREADS=1
LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/mnt/nfshare/lib

{monitor_block}
SECONDS=0
mpirun {exe} {tcl_file}

[ -n "$MONITOR_PID" ] && kill "$MONITOR_PID" 2>/dev/null

echo "Elapsed: $SECONDS seconds."
echo "Code finished successfully."
echo "LARGA VIDA AL LADRUÑO!!!"
""")
        
        script_path = self.path / script_name
        script_path.write_text("\n".join(header) + "\n" + body)
        script_path.chmod(0o755)
        
        if self.verbose:
            print(f"📝 run.sh created (nodes={nodes}, ntasks={ntasks})")
        
        return script_path