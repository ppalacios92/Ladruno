# Ladruno

**Ladruno** is a Python package for automating the execution, tracking, and archiving of OpenSeesMP simulations on SLURM-based clusters. It provides a unified interface to manage single or multiple models automatically.

## ✨ Features

- 🤖 **Auto-detection**: Automatically detects single model or recursively finds multiple models
- 📝 **SLURM script generation**: Creates optimized `run.sh` scripts with proper node/task allocation
- 📊 **RAM monitoring**: Optional process memory tracking during execution
- 💾 **Smart archiving**: Moves completed simulations to archive storage with cleanup
- 🔧 **HDF5 repair**: Fixes "open for write" flags in `.mpco` files using `h5clear`
- 🎯 **Partition detection**: Automatically counts OpenSees partitions from `.mpco.cdata` files

---

## 📦 Installation

From the root of the repository:
```bash
pip install -e .
```

**Requirements:**
- Python ≥ 3.10
- `h5py`
- `h5clear` (part of `hdf5-tools` package)
- SLURM (`sbatch`, `squeue`, `mpirun`)

---

## 📂 Project Structure
```
Ladruno/
├── core/
│   ├── model.py        # Unified Model class (single/multi auto-detection)
│   └── __init__.py
├── engine/
│   ├── run.py          # Run class for SLURM job management
│   └── __init__.py
├── utilities/
│   ├── h5.py           # H5RepairTool for HDF5 file repair
│   └── __init__.py
└── __init__.py         # Top-level API
```

---

## 🚀 Quick Start

### 1. Basic Usage (Single or Multiple Models)
```python
from Ladruno import Model

# Works for both single model or folder with multiple models
model = Model(
    path="/mnt/deadmanschest/pxpalacios/TEST_ESMERALDA/",
    verbose=True,
    opensees_exe='/mnt/nfshare/bin/opensees-14072025',
    archive_destination='/mnt/krakenschest/home/pxpalacios'
)

# Submit all detected models
exclude_nodes = [f"node{n}" for n in range(1, 17)]
model.submit(
    exclude=exclude_nodes,
    monitor_ram=True,
    archive=True
)
```

### 2. Single Model
```python
from Ladruno import Model

# If path contains main.tcl directly
model = Model(
    path="/path/to/single_model/",
    number_of_nodes=2,
    verbose=True
)

model.submit(rebuild=True, archive=False)
```

### 3. Multiple Models (Recursive Search)
```python
from Ladruno import Model

# If path contains subfolders with main.tcl files
model = Model(
    path="/path/to/multiple_models/",
    max_nodes=18,
    max_tasks_per_node=32,
    verbose=True
)

# Submits all found models
job_ids = model.submit(
    monitor_ram=True,
    archive=True
)

print(f"Submitted {len(job_ids)} jobs: {job_ids}")
```

### 4. HDF5 Repair Tool Only
```python
from Ladruno.utilities import H5RepairTool

fixer = H5RepairTool(
    directory="/path/to/folder",
    pattern="*.mpco",
    verbose=True
)
fixer.run_full_check_and_fix()
```

---

## 📋 Generated Files

After submission, the following files are created in each model folder:

- `run.sh`: SLURM batch script
- `log.log`: OpenSees output and execution log
- `memtrack_node.txt`: RAM usage log (if `monitor_ram=True`)
- `status.txt`: Execution metadata and archive information

---

## 📄 Example `run.sh`

**Without archive:**
```bash
#!/bin/bash
#SBATCH --job-name=01
#SBATCH --output=log.log
#SBATCH --nodes=1
#SBATCH --ntasks=2
#SBATCH --exclude=node1,node2,node3

pwd; hostname; date
export OMP_NUM_THREADS=1
LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/mnt/nfshare/lib

SECONDS=0
mpirun /mnt/nfshare/bin/opensees-14072025 main.tcl

[ -n "$MONITOR_PID" ] && kill "$MONITOR_PID" 2>/dev/null

echo "Elapsed: $SECONDS seconds."
echo "Code finished successfully."
echo "LARGA VIDA AL LADRUÑO!!!"
```

**With archive:**
```bash
#!/bin/bash
#SBATCH --job-name=01
#SBATCH --output=log.log
#SBATCH --nodes=1
#SBATCH --ntasks=2

pwd; hostname; date
export OMP_NUM_THREADS=1
LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/mnt/nfshare/lib

SECONDS=0
mpirun /mnt/nfshare/bin/opensees-14072025 main.tcl

[ -n "$MONITOR_PID" ] && kill "$MONITOR_PID" 2>/dev/null

EXIT_CODE=$?
DURATION=$SECONDS

# Forzar EXIT_CODE=0 si hay SUCCESS en el log
if grep -q "SUCCESS" log.log 2>/dev/null; then
    EXIT_CODE=0
fi

echo "Elapsed: $DURATION seconds."
echo "Code finished with exit code $EXIT_CODE."

# Archive block: moves folder and cleans up
...

echo "LARGA VIDA AL LADRUÑO!!!"
```

---

## 🎛️ Configuration Options

### Model Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `path` | (required) | Path to model folder or parent folder |
| `number_of_nodes` | 1 | Minimum nodes to request |
| `max_nodes` | 18 | Maximum nodes allowed |
| `max_tasks_per_node` | 32 | Tasks per node limit |
| `verbose` | False | Enable detailed logging |
| `opensees_exe` | `/mnt/nfshare/bin/openseesmp-26062025` | Path to OpenSees executable |
| `archive_destination` | `/mnt/krakenschest/home/pxpalacios` | Archive base directory |

### Submit Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `archive` | False | Move folder to archive after completion |
| `rebuild` | True | Regenerate `run.sh` before submit |
| `monitor_ram` | False | Track RAM usage during execution |
| `exclude` | None | List of nodes to exclude (e.g., `['node1', 'node2']`) |
| `nodes` | None | Override detected node count |
| `ntasks` | None | Override detected task count |

---

## 🔍 How It Works

1. **Detection**: `Model` searches for `main.tcl` files
   - Found directly? → Single model mode
   - Found in subfolders? → Multiple model mode (recursive)

2. **Partition Analysis**: Counts `.mpco.cdata` files to determine required tasks

3. **Resource Allocation**: Calculates optimal `nodes` and `ntasks` for SLURM

4. **Script Generation**: Creates `run.sh` with proper SLURM directives

5. **Submission**: Executes `sbatch` and returns job ID(s)

6. **Archiving** (optional):
   - Waits for job completion
   - Detects "SUCCESS" in output
   - Copies folder to archive destination
   - Cleans up original folder (keeps `status.txt`)

---

## 👨‍💻 Contributing

To contribute:
1. Fork the repository
2. Create a feature branch
3. Write code + tests
4. Submit a pull request

---

## 📄 License

MIT License © Nicolas Mora Bowen - Patricio Palacios

**LARGA VIDA AL LADRUÑO!!!** 🏴‍☠️