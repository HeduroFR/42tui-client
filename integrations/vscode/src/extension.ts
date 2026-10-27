import { execFile } from "node:child_process";
import * as vscode from "vscode";

const HEARTBEAT_INTERVAL_MS = 30_000;

export function activate(context: vscode.ExtensionContext): void {
    const output = vscode.window.createOutputChannel("42TUI Activity");
    context.subscriptions.push(output);

    let lastFile: string | undefined;
    let lastHeartbeatAt = 0;
    let missingCliReported = false;

    const sendHeartbeat = (document: vscode.TextDocument, isWrite = false): void => {
        const config = vscode.workspace.getConfiguration("42tui");
        if (!config.get<boolean>("enabled", true) || document.uri.scheme !== "file") {
            return;
        }

        const filePath = document.uri.fsPath;
        const now = Date.now();
        if (!isWrite && filePath === lastFile && now - lastHeartbeatAt < HEARTBEAT_INTERVAL_MS) {
            return;
        }

        const cliPath = config.get<string>("cliPath", "42tui");
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
