import { tmpdir } from "node:os";
import path from "node:path";

export const resultsRoot = path.resolve(
  process.env.ZET_TEST_RESULTS_ROOT || path.join(tmpdir(), "Zet-test-results", path.basename(process.cwd())),
);
