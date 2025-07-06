# Ladruno

**Ladruno** is a Python package for automating the execution, tracking, and archiving of OpenSeesMP simulations on SLURM-based clusters. It includes tools to:

- Automatically generate SLURM `run.sh` scripts
- Monitor RAM usage of OpenSees processes
- Fix HDF5 "open for write" flags using `h5clear`
- Move simulation folders after completion and maintain an archive log

---

## 📦 Installation

From the root of the repository:

```bash
pip install -e .
```

Make sure `h5py` and `h5clear` are available in your environment.

---

## 📂 Project Structure

```
Ladruno/
├── core/               # Future model management tools
├── multiple_file/      # (reserved)
├── single_file/
│   └── run.py          # Run class definition
├── utilities/
│   └── h5.py           # H5RepairTool
└── __init__.py         # Top-level API
```

---

## 🚀 Quick Start

### 1. Basic Usage

```python
from Ladruno import Run

r = Run("path/to/folder", verbose=True)
r.submit()
```

> This will:
> - Detect how many `.mpco` partitions are present
> - Generate `run.sh`
> - Submit the SLURM job
> - Wait for it to finish
> - Fix HDF5 flags
> - Move the folder to your archive directory

---

### 2. Manual Workflow (Advanced)

```python
from Ladruno import Run, H5RepairTool

# Create a runner object
runner = Run("/mnt/deadmanschest/nmorabowen/test01", verbose=True)

# Build SLURM script only
runner.build_run_script()

# Submit without auto-move
job_id = runner.submit(archive=False)

# Optionally fix flags and move manually
runner.archive_after_finish(job_id)
```

---

### 3. HDF5 Flag Fixer Only

```python
from Ladruno.utilities import H5RepairTool

fixer = H5RepairTool(directory="path/to/folder", pattern="*.mpco")
fixer.run_full_check_and_fix(verbose=True)
```

---

## 📋 Output Files

After submission, the following files are generated:

- `run.sh`: SLURM job script
- `log.log`: OpenSees standard output
- `memtrack_node.txt`: Optional RAM log
- `archive_moves.log`: Cumulative log of moved jobs

---

## 📄 Example `run.sh`

```bash
#!/bin/bash
#SBATCH --job-name=test01
#SBATCH --nodes=2
#SBATCH --ntasks=32
#SBATCH --ntasks-per-node=16
#SBATCH --output=log.log

pwd; hostname; date
export OMP_NUM_THREADS=1
LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/mnt/nfshare/lib

# RAM Monitor Starts
...

mpirun /mnt/nfshare/bin/openseesmp-26062025 main.tcl

# RAM Monitor Ends
...
```

---

## 🛠 Requirements

- Python ≥ 3.10
- `h5py`
- `h5clear` (part of the `hdf5-tools` package on most Linux distros)
- SLURM and `sbatch`, `squeue`, `mpirun` available in `$PATH`

---

## 👨‍💻 Contributing

To contribute:

1. Fork the repo
2. Create a branch
3. Write code + tests
4. Submit a pull request

Pre-commit hooks and mypy configs are provided.

---

## 📄 License

MIT License © Nicolas Mora Bowen / Patricio Palacios
LARGA VIDA AL LADRUÑO!!!
