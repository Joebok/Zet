# Naming Conventions

For each type of these scripts:

* Polling 
* Worker
* State-Change
* House-Keeping
* AI-Handler
* Batch

Name them after the State field they manage. For example, PipelineStage is a state field and so will have

pipeline_Polling.py
pipeline_Worker.py
pipeline_Housekeeping.py
pipeline_AIHander.py
pipeline_Batch.py

These will the master functions to manage that state field, they may call other scripts for specific tasks. The other scripts should be in a subfolder of the Scripts\ folder. For example

Scripts\pipeline\Manifest.py

might become a script that pipeline_Worker.py calls to do work related to changing PipelineStage to MANIFEST.

## Parameters

Except for Batch, each script will operate on one Asset. The AssetID needs to be in every argument list. All scripts should have arguments to return an Error message. Consuming scripts need to either deal with the error or pass it up the chain.

State-Change scripts will additionally need the State that they need to change to.

## AI_Manager

Will have it's own set of scripts, not yet detailed at this time. Plan for them to be in Scripts/AI_Manager