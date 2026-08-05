#!/bin/bash

#SBATCH --job-name=mthesis_base_problem_copt
#output paths have to adjusted to your folders
#SBATCH --output=/scratch/htc/lmehl/master_thesis/base_problems/copt/results/job_out/sbatch_job_%A.out
#SBATCH --error=/scratch/htc/lmehl/master_thesis/base_problems/copt/results/job_out/sbatch_job_%A.err
#SBATCH --partition=big
#SBATCH --time=1:00:00
#SBATCH --cpus-per-task=8
#SBATCH --mem=10G

echo "solve with copt"
echo "called script: $0"
lpfile="$1"
echo "instance: $lpfile"
prmfile="$2"
echo "parameters $prmfile"

echo "CPUs per task: $SLURM_CPUS_PER_TASK"
echo "Requested memory per node: $((SLURM_MEM_PER_NODE / 1024)) GiB ($(awk -v m="$SLURM_MEM_PER_NODE" 'BEGIN { printf "%.2f", m*1024*1024/1e9 }') GB)"

NUM_RUNS="$3"
echo "NUM_RUNS = ${NUM_RUNS}"

#TODO: paths for copt, incl. license
export COPT_HOME=/software/COPT/copt80
export COPT_LICENSE_DIR=/software/COPT/copt80/ziblic/
export PATH=$COPT_HOME/bin:$PATH
#export DYLD_LIBRARY_PATH=$COPT_HOME/lib:$DYLD_LIBRARY_PATH
export LD_LIBRARY_PATH=$COPT_HOME/lib:$LD_LIBRARY_PATH

#for usage at z1 cluster set http and https proxy environment variables
export https_proxy=http://squid.zib.de:3128
export http_proxy=http://squid.zib.de:3128 

lp_name_w_suffix=$(basename "$lpfile")
lp_name="${lp_name_w_suffix%.lp}"
timestamp=$(date +%Y-%m-%d_%H-%M-%S)
prmfile_basename="$(basename "${prmfile}")"

solfolder="/scratch/htc/lmehl/master_thesis/base_problems/copt/results/${lp_name}/run_${timestamp}_${prmfile_basename}"
mkdir -p $solfolder

echo "solution folder: ${solfolder}"

cp $prmfile $solfolder 

copied_prmfile="${solfolder}/${prmfile_basename}"

echo "------ Hardware info: ------"
#info on cpu details
lscpu
echo "------ (end of hardware info) ------"

source ~/conda_init
conda activate copt

for (( i=0; i<NUM_RUNS; i++ )); do
    /usr/bin/time -v \
        python /scratch/htc/lmehl/master_thesis/base_problems/copt/solve_lp_w_copt.py \
        "$lpfile" "$solfolder" "$copied_prmfile" \
        2>&1

    echo "Run $i completed."
done

