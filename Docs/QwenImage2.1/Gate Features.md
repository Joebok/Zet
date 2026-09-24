# Create a plan for gate features:

Overall goal is to better mange gate testing by providing currated test cases that can be used to validate the gate, do regression tests for changes, and to simplify the model parameter options for testing.

## Configuration

For each local pipeline, have a "setup" option available at the top of the page.
When opened, it should list all gates for that local pipeline.
For each gate, have a selectable status of either:
"Active"
"Warning"
"Disabled"

An active gate means it runs and if failed, fails the image.
A warning gate means it runs and if failed, shows a warning but doesn't affect anything else.
A disable gate means it does not run but is still listed as disabled.

Update the review process to honor these gate statuses. For all existing gates, mark them active except for the body-reference orientation which should remain disabled.

## Testing

Update the Gate Test Rig

Add the ability to save, rename, and delete a test. A "test" is a local pipeline, a gate of that pipeline, the configuration (AI model and parameters) used for the last run, prompt overrides, the test cases used (or reference ids for the test cases), and the gate results for that test case. Saving a test after a run or re-run replaces all the old values.

Add a "New Test" button to give the user a way to make a new test.

At the top, the user must select from one of the local pipelines.

Once the pipeline is selected, they can select the gate. 

However, instead of selecting a run and view for test data, a currated set of test images is used.

For the model request section, I just want to have inputs for API endpoint, model or alias, and thinking. Temperature and Keep alive should be removed and not overriden. 

After a test run, have a "Save Test" button.

Remove the saved configuration mechanism. This should all be captured under the save test functionality.

## Curated Test Data

From any of the reviews of a local pipeline image, add a "Add to Gate Test Data" button. This button should then ask which gate (offering a selection of all available gates it was subject to - including warning and disabled) and it should ask what the correct answer is - to PASS the image or FAIL the image based on that gate. Then when saved, the image along with the associated view and correct answer should be stored in a folder dedicated to test cases for that gate. 

Additionally, from the Gate Test Rig, the user should be able to add test cases by pasting in an image, indicate what view should be tagged and what the correct answer for the designated gate should be.

There should be a review test data page where the test cases can be viewed, edited, or deleted.

## Backward Compatability

For these enhancements, NO backward compatability is required. Existing tests and configurations should be discarded.

## Review Packet

Add a button to create a "review packet" for a test. Using the saved test information, create a zip file with all of the config, test cases, and diagnostic information that is available for that test run.
