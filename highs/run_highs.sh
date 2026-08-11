#!/bin/bash

#SBATCH --job-name=mthesis_base_problem_highs
#output paths have to adjusted to your folders
#SBATCH --output=/scratch/htc/lmehl/master_thesis/base_problems/highs/results/job_out/sbatch_job_%A.out
#SBATCH --error=/scratch/htc/lmehl/master_thesis/base_problems/highs/results/job_out/sbatch_job_%A.err
#SBATCH --partition=big
#SBATCH --time=1:00:00
#SBATCH --constraint=Gold6338
#SBATCH --mem=10G
#SBATCH --cpus-per-task=8
#SBATCH --hint=nomultithread
#SBATCH --cpu-freq=medium-medium:Performance

#for usage at z1 cluster set http and https proxy environment variables
export https_proxy=http://squid.zib.de:3128
export http_proxy=http://squid.zib.de:3128 

echo "solve with highs"
echo "script: $0"
lpfile="$1"
echo "instance: $lpfile"
prmfile="$2"
echo "parameters $prmfile"

NUM_RUNS="$3"
echo "NUM_RUNS = ${NUM_RUNS}"

lp_name_w_suffix=$(basename "$lpfile")
lp_name="${lp_name_w_suffix%.lp}"
timestamp=$(date +%Y-%m-%d_%H-%M-%S)
prmfile_basename="$(basename "${prmfile}")"

solfolder="/scratch/htc/lmehl/master_thesis/base_problems/highs/results/${lp_name}/run_${timestamp}_${prmfile_basename}"
mkdir -p $solfolder

echo "solution folder: ${solfolder}"

cp $prmfile $solfolder 

copied_prmfile="${solfolder}/${prmfile_basename}"

echo "------ SLURM allocation info ------"
echo "Job ID: ${SLURM_JOB_ID:-unknown}"
echo "Allocated node(s): ${SLURM_JOB_NODELIST:-unknown}"
echo "CPUs per task: ${SLURM_CPUS_PER_TASK:-not explicitly set}"
echo "CPUs allocated on node: ${SLURM_CPUS_ON_NODE:-unknown}"

echo "Batch-shell CPU affinity:"
taskset -cp $$ || true

echo "SLURM job information:"
scontrol show job "$SLURM_JOB_ID" | grep -E \
    'JobId=|NodeList=|NumNodes=|NumCPUs=|ReqTRES=|AllocTRES=|ReqS:C:T=|ReqB:S:C:T=' \
    || true

echo "Actual task affinity using srun:"
srun --cpu-bind=quiet bash -c '
    echo "Task PID: $$"
    taskset -cp $$
    echo "CPU/core mapping:"
    ALLOWED_CPUS=$(taskset -pc $$ | awk -F": " "{print \$2}")
    lscpu -p=CPU,CORE,SOCKET,NODE | grep -v "^#" |
    awk -F, -v allowed="$ALLOWED_CPUS" "
    BEGIN {
        n = split(allowed, ranges, \",\")
        for (i = 1; i <= n; i++) {
            if (ranges[i] ~ /-/) {
                split(ranges[i], r, \"-\")
                for (j = r[1]; j <= r[2]; j++)
                    a[j] = 1
            } else {
                a[ranges[i]] = 1
            }
        }
    }
    a[\$1] {
        printf \"CPU %-4s CORE %-4s SOCKET %-2s NUMA %-2s\n\", \$1, \$2, \$3, \$4
    }"
'

echo "CPU frequency SBATCH setting:"
grep -E '^#SBATCH[[:space:]]+--cpu-freq(=|[[:space:]])' "$0" \
    || echo "#SBATCH --cpu-freq: not set"

echo "SLURM CPU frequency request: ${SLURM_CPU_FREQ_REQ:-not reported}"

echo "SBATCH hint setting:"
grep -E '^#SBATCH[[:space:]]+--hint(=|[[:space:]])' "$0" \
    || echo "#SBATCH --hint: not set"

echo "Requested memory per node: \
$((SLURM_MEM_PER_NODE / 1024)) GiB \
($(awk -v m="$SLURM_MEM_PER_NODE" \
'BEGIN { printf "%.2f", m*1024*1024/1e9 }') GB)"

echo "------ (end of SLURM allocation info) ------"

echo "------ Hardware info: ------"
lscpu
echo "------ (end of hardware info) ------"

source ~/conda_init
conda activate

cd $solfolder

#solve once and store the sol file
timestamp=$(date +%Y-%m-%d_%H-%M-%S)
sol_file="${solfolder}/${lp_name}_${timestamp}.highs.sol"

/usr/bin/time -v /scratch/htc/lmehl/setup/HiGHS/build/bin/highs $lpfile \
    --solution_file=$sol_file --options_file $copied_prmfile \
    2> "${solfolder}/time_run_0.log"

gzip $sol_file
echo "Run completed."

#solve 2 more times but without storing sol file
for (( i=1; i<NUM_RUNS; i++ )); do
    /usr/bin/time -v /scratch/htc/lmehl/setup/HiGHS/build/bin/highs $lpfile \
        --options_file $copied_prmfile \
        2> "${solfolder}/time_run_${i}.log"
        
    echo "Run completed."
done
