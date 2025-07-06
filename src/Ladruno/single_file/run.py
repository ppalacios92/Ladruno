from __future__ import annotations
from pathlib import Path
from typing import Sequence, Optional
import re
import subprocess
import textwrap
import shutil
import time
from datetime import datetime
from pathlib import Path
import h5py

from Ladruno.utilities.h5 import H5RepairTool

class Run:
    def __init__(self,
                 folder_path: str,
                 number_of_nodes: int = 1,
                 max_nodes: int = 18,
                 max_tasks_per_node: int = 32,
                 verbose: bool = False,
                 opensees_exe: str | Path = "/mnt/nfshare/bin/openseesmp-26062025"):
        
        self.path = Path(folder_path).resolve()
        self.number_of_nodes = number_of_nodes
        self.max_nodes = max_nodes
        self.max_tasks_per_node = max_tasks_per_node
        self.verbose = verbose
        self.opensees_exe = Path(opensees_exe).resolve()
        
        self.fix: H5RepairTool  = H5RepairTool(
            directory = self.path,
            pattern = "*.mpco",
            verbose= self.verbose)
        
        if not (self.path / "main.tcl").exists():
            raise FileNotFoundError(f"main.tcl not found in: {self.path}")
        
    def get_folder_name(self) -> str:
        """Return the folder name (last path component)."""
        return self.path.name

    def get_tasks(self) -> int:
        """
        Return the number of OpenSees partitions → Slurm `--ntasks`.

        Logic
        -----
        • Look for any file that matches
          `*.part-<N>.mpco` **or** `*.part-<N>.mpco.cdata`.
        • Collect all distinct `<N>` integers.
        • If nothing is found → assume a serial run → return **1**.
        • Otherwise:
            * `max_idx`  = max(indexes) + 1
            * `unique`   = len(indexes)
            * If there are missing parts (holes in numbering), choose the
              larger of the two so we don’t under-allocate.
        """
        part_rx = re.compile(r"\.part-(\d+)\.mpco.cdata$")

        indices: set[int] = {
            int(m.group(1))
            for p in self.path.glob("**/*.mpco.cdata")
            if (m := part_rx.search(p.name))
        }

        if not indices:            # no partitioned files found
            return 1

        max_idx  = max(indices) + 1
        unique   = len(indices)
        
        if self.verbose:
            print(f"Found {unique} unique partitions, max index is {max_idx - 1}.")

        return max(max_idx, unique)
    
    def get_nodes_and_tasks(self) -> tuple[int, int]:
        """
        Compute the Slurm node/task configuration based on available partitions and node size.
        """
        ntasks_required = max(self.get_tasks(), 1)
        tpn = max(self.max_tasks_per_node, 1)

        # Determine the minimum required nodes to fit all tasks
        min_nodes = (ntasks_required + tpn - 1) // tpn  # ceil division

        # Enforce upper and lower bounds
        nodes = max(min_nodes, self.number_of_nodes)
        if nodes > self.max_nodes:
            if self.verbose:
                print(f"⚠️ Requested too many nodes ({nodes}) — capping to max_nodes={self.max_nodes}")
            nodes = self.max_nodes

        # Validate that capped node count is still sufficient
        if nodes * tpn < ntasks_required:
            raise ValueError(
                f"Cannot fit {ntasks_required} tasks in {nodes} node(s) × {tpn} tasks/node"
            )

        if self.verbose:
            print(f"📦 get_nodes_and_tasks → nodes={nodes}, ntasks={ntasks_required}")
        return nodes, ntasks_required
            
    def submit(
        self,
        *,
        archive: bool = False,         # wait, fix flags, then move folder
        fix: bool = True,             # clear HDF5 “open-for-write” flags
        rebuild: bool = True,         # regenerate run.sh before sbatch
        job_name: str | None = None,
        nodes: int | None = None,
        ntasks: int | None = None,
        ntasks_per_node: int | None = None,
        exclude: Sequence[str] | None = None,
        tcl_file: str = "main.tcl",
        monitor_ram: bool = True,
        monitor_interval: int = 30,
        log_file: str = "memtrack_node.txt",
    ) -> int:
        """
        Submit the Slurm job and (optionally) archive it when finished.

        Parameters
        ----------
        archive : bool
            If True (default), waits for job completion, then runs
            `archive_after_finish()` which fixes HDF5 flags and moves
            the folder.
        fix : bool
            Passed to `archive_after_finish(fix_flags=…)`. Controls
            whether the HDF5 flag repair is executed.
        rebuild : bool
            If True, regenerate run.sh via `build_run_script()`.

        Returns
        -------
        int
            The submitted Slurm job ID.
        """
        # 1. Build run.sh (optional)
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
                archive=archive,
            )

        script = self.path / "run.sh"
        # 2. Submit job
        try:
            proc = subprocess.run(
                ["sbatch", str(script)],
                capture_output=True,
                text=True,
                check=True,
                cwd=self.path
            )
            # 🔍 Mostrar la salida y errores por consola

            job_id = int(proc.stdout.split()[-1])
            if self.verbose:
                print(f"🚀 Submitted batch job {job_id}")
        except subprocess.CalledProcessError as e:
            print("❌ Failed to submit job:\n", e.stderr)
            raise



        return job_id


    
    @staticmethod
    def _ram_monitor_block(
        *,
        interval: int = 30,
        log_file: str = "memtrack_node.txt",
        grep_term: str = "openseesmp",
    ) -> str:
        """
        Returns a Bash snippet that:

        • Appends timestamp + `free -h` to *log_file*
        • For every PID whose cmdline contains *grep_term*, also logs:
          `ps -p PID -o pid,%mem,rss,vsz,cmd`
        • Repeats every *interval* seconds in the background and saves
          its PID to MONITOR_PID so we can `kill $MONITOR_PID` later.
        """
        
        return textwrap.dedent(f"""\
            # --- RAM monitor starts (interval={interval}s) ---
            ( while true; do
                printf '%s\\n' "$(date '+%F %T')" >> {log_file}
                free -h >> {log_file}
                echo "-----------" >> {log_file}
                pgrep -af {grep_term} | while read PID CMD; do
                    echo "PID: $PID" >> {log_file}
                    ps -p "$PID" -o pid,%mem,rss,vsz,cmd --no-headers >> {log_file}
                done
                echo "======================" >> {log_file}
                sleep {interval}
            done & )
            MONITOR_PID=$!
        """)




    import textwrap

    def move_and_cleanup_block(self) -> str:

        # source_root: str | Path = "/mnt/deadmanschest/pxpalacios",
        # dest_root:   str | Path = "/mnt/krakenschest/home/pxpalacios",

        """
        Returns a Bash block that:
        - Captures runtime and exit code
        - Logs metadata to status.txt
        - Moves the job directory to krakenschest
        - Cleans up original folder if successful
        """
        return textwrap.dedent("""\
            # --- Postproceso: mover carpeta si el job terminó correctamente ---
            EXIT_CODE=$?
            DURATION=$SECONDS

            echo "Elapsed: $DURATION seconds."
            echo "Code finished with exit code $EXIT_CODE."
            echo "LARGA VIDA AL LADRUÑO!!!"

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
        """)


    def build_run_script(
        self,
        *,
        job_name: str | None = None,
        # ---------- resources ------------------------------------------------
        nodes: int | None = None,
        ntasks: int | None = None,
        ntasks_per_node: int | None = None,
        exclude: Sequence[str] | None = None,
        # ---------- executable / input --------------------------------------
        exe: str | Path = "/mnt/nfshare/bin/openseesmp-26062025",
        tcl_file: str = "main.tcl",
        # ---------- optional RAM monitor ------------------------------------
        monitor_ram: bool = False,
        monitor_interval: int = 30,
        log_file: str = "memtrack_node.txt",
        # ---------- optional MOVE -------------------------------------------
        archive: bool = False,         # wait, fix flags, then move folder
        # ---------- misc -----------------------------------------------------
        script_name: str = "run.sh",
    ) -> Path:
        """
        Generate *run.sh* in the analysis folder and return its Path.

        The script now focuses solely on running OpenSees (plus optional RAM
        tracking).  Moving / fixing is handled later by `archive_after_finish`.
        """
        # -------------------- compute resources -----------------------------
        if nodes is None or ntasks is None:
            nodes, ntasks = self.get_nodes_and_tasks()
        if ntasks_per_node is None:
            ntasks_per_node_cal = (ntasks + nodes - 1) // nodes  # ceil

        job_name = job_name or self.get_folder_name()

        # -------------------- Slurm header ----------------------------------
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
        

        # -------------------- optional RAM monitor --------------------------
        monitor_block = (
            self._ram_monitor_block(interval=monitor_interval, log_file=log_file)
            if monitor_ram
            else ""
        )
        # -------------------- run_move --------------------------
        if archive:
            run_move=self.move_and_cleanup_block()
        else:
            run_move=""

        # -------------------- main body -------------------------------------
        body = textwrap.dedent(f"""\
pwd; hostname; date
export OMP_NUM_THREADS=1
LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/mnt/nfshare/lib

{monitor_block}
SECONDS=0
mpirun {exe} {tcl_file}

# stop monitor (if running)
[ -n "$MONITOR_PID" ] && kill "$MONITOR_PID" 2>/dev/null

echo "Elapsed: $SECONDS seconds."
echo "Code finished successfully."
echo "LARGA VIDA AL LADRUÑO!!!"
{run_move}
""")



        script_path = self.path / script_name
        script_path.write_text("\n".join(header) + "\n" + body)
        script_path.chmod(0o755)

        if self.verbose:
            print(
                f"📝 Wrote {script_path} "
                f"(nodes={nodes}, ntasks={ntasks}, "
                f"ntasks/node={ntasks_per_node}, "
                f"RAM monitor={'on' if monitor_ram else 'off'})"
            )
        return script_path