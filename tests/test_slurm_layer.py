from qbacmetc.slurm_layer import SlurmLayer

if __name__ == "__main__":
    slurm = SlurmLayer()

    print("Partitions:", slurm.get_partitions())
    print("Nodes:", slurm.get_nodes())
    print("Node Resources:", slurm.get_node_resources())
    print("Partition Limits:", slurm.get_partition_limits())
    print("Node States:", slurm.get_node_states())
    print("Node Load:", slurm.get_node_load())
    # To test job resource usage, provide a valid job ID:
    # print("Job Resource Usage:", slurm.get_job_resource_usage(<jobid>))
