"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { execFile } = require("node:child_process");
const vscode = require("vscode");

const HEARTBEAT_INTERVAL_MS = 30_000;

function cliCandidates(context) {
    const configured = vscode.workspace.getConfiguration("42tui").get("cliPath", "").trim();
    const candidates = [];
    if (configured) {
        candidates.push(configured);
    }
    if (process.env.FT_TUI_EXECUTABLE) {
        candidates.push(process.env.FT_TUI_EXECUTABLE);
    }
    try {
        const injected = fs.readFileSync(path.join(context.extensionPath, "42tui-path.txt"), "utf8").trim();
        if (injected) {
            candidates.push(injected);
        }
    } catch {
        // The installer always injects this file; a source-tree run may not have it.
    }
    const home = process.env.HOME || process.env.USERPROFILE;
    if (home) {
        candidates.push(
            path.join(home, ".local", "bin", "42tui"),
            path.join(home, ".local", "pipx", "venvs", "ft-tui", "bin", "42tui"),
        );
    }
    candidates.push("/opt/homebrew/bin/42tui", "/usr/local/bin/42tui");
    return candidates;
}

function resolveCli(context) {
    for (const candidate of cliCandidates(context)) {
        try {
            if (fs.statSync(candidate).isFile()) {
                fs.accessSync(candidate, fs.constants.X_OK);
                return candidate;
            }
        } catch {
            // Try the next candidate.
        }
    }
    return "42tui";
}

function activate(context) {
    const output = vscode.window.createOutputChannel("42TUI Activity");
    context.subscriptions.push(output);

    const cliPath = resolveCli(context);
    let lastFile;
    let lastHeartbeatAt = 0;
    let missingCliReported = false;

    const sendHeartbeat = (document, isWrite = false) => {
        const config = vscode.workspace.getConfiguration("42tui");
        if (!config.get("enabled", true) || document.uri.scheme !== "file") {
            return;
        }

        const filePath = document.uri.fsPath;
        const now = Date.now();
        if (!isWrite && filePath === lastFile && now - lastHeartbeatAt < HEARTBEAT_INTERVAL_MS) {
            return;
        }

        const args = ["heartbeat", "--file", filePath, "--editor", "vscode", "--quiet"];
        if (isWrite) {
            args.push("--write");
        }

        // Reserve the slot before spawning so rapid document-change events don't fork
        // a burst of CLI processes while the first heartbeat is still being recorded.
        lastFile = filePath;
        lastHeartbeatAt = now;
        execFile(cliPath, args, { windowsHide: true }, (error, _stdout, stderr) => {
            if (error) {
                lastHeartbeatAt = 0;
                if (!missingCliReported) {
                    output.appendLine(`Could not run ${cliPath}: ${error.message}`);
                    if (stderr.trim()) {
                        output.appendLine(stderr.trim());
                    }
                    missingCliReported = true;
                }
                return;
            }
            missingCliReported = false;
        });
    };

    const activeEditor = vscode.window.activeTextEditor;
    if (activeEditor) {
        sendHeartbeat(activeEditor.document);
    }

    context.subscriptions.push(
        vscode.window.onDidChangeActiveTextEditor((editor) => {
            if (editor) {
                sendHeartbeat(editor.document);
            }
        }),
        vscode.workspace.onDidChangeTextDocument((event) => {
            const active = vscode.window.activeTextEditor;
            if (active?.document === event.document && event.contentChanges.length > 0) {
                sendHeartbeat(event.document);
            }
        }),
        vscode.workspace.onDidSaveTextDocument((document) => sendHeartbeat(document, true)),
    );
}

function deactivate() {}

module.exports = { activate, deactivate, resolveCli };
