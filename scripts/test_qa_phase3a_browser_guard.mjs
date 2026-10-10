import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdtemp, access, rm } from "node:fs/promises";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { promisify } from "node:util";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
    assertDisposableQADatabase,
    EXPECTED_QA_DATABASE,
} from "./qa_phase3a_browser_guard.mjs";

const execFileAsync = promisify(execFile);
const browserScript = fileURLToPath(new URL("./qa_phase3a_browser.mjs", import.meta.url));

test("the QA guard accepts only the named throwaway database", () => {
    assert.doesNotThrow(() => assertDisposableQADatabase(EXPECTED_QA_DATABASE));
    for (const database of [
        "autostock_showroom_demo",
        "autostock_phase3a_qa_copy",
        "postgres",
        "production",
        "",
        undefined,
    ]) {
        assert.throws(() => assertDisposableQADatabase(database), /Refusing browser QA writes/);
    }
});

test("an invalid database exits before login, network access or screenshot writes", async () => {
    let requests = 0;
    const server = http.createServer((_request, response) => {
        requests += 1;
        response.writeHead(200, { "content-type": "text/html" });
        response.end("Unexpected QA request");
    });
    await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
    const address = server.address();
    const tempDirectory = await mkdtemp(path.join(os.tmpdir(), "autostock-qa-guard-"));
    const screenshotDirectory = path.join(tempDirectory, "must-not-be-created");
    try {
        await assert.rejects(
            execFileAsync(process.execPath, [browserScript], {
                env: {
                    ...process.env,
                    AUTOSTOCK_QA_DB: "autostock_showroom_demo",
                    AUTOSTOCK_QA_URL: `http://127.0.0.1:${address.port}`,
                    AUTOSTOCK_QA_LOGIN: "must-not-login",
                    AUTOSTOCK_QA_PASSWORD: "not-a-secret",
                    AUTOSTOCK_QA_SCREENSHOT_DIR: screenshotDirectory,
                    PLAYWRIGHT_MODULE: "this-module-must-not-be-loaded",
                },
                encoding: "utf8",
                timeout: 5000,
            }),
            (error) => {
                const output = `${error.stdout || ""}\n${error.stderr || ""}`;
                assert.match(output, /AUTOSTOCK_QA_DB must be exactly autostock_phase3a_qa/);
                assert.doesNotMatch(output, /this-module-must-not-be-loaded|must-not-login/);
                return true;
            }
        );
        assert.equal(requests, 0, "An invalid database reached the local Odoo endpoint.");
        await assert.rejects(access(screenshotDirectory), { code: "ENOENT" });
    } finally {
        await new Promise((resolve) => server.close(resolve));
        await rm(tempDirectory, { recursive: true, force: true });
    }
});
