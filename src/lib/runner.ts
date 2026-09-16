import { spawn } from 'child_process';

/**
 * CommandRunner abstraction for secure system command execution.
 * 
 * SECURITY CONSTRAINTS:
 * 1. Absolute zero string concatenation. Arguments are passed as an array to spawn(), preventing shell injection.
 * 2. Strict whitelist of allowed base commands.
 * 3. No shell: true.
 */

const ALLOWED_COMMANDS = new Set([
  'uptime',
  'free',
  'df',
  'systemctl',
  'ping',
  'apt-get',
  'uname'
]);

export interface CommandResult {
  stdout: string;
  stderr: string;
  exitCode: number | null;
}

export async function runCommand(cmd: string, args: string[] = [], timeoutMs = 10000): Promise<CommandResult> {
  // 1. Strict Whitelist Check
  if (!ALLOWED_COMMANDS.has(cmd)) {
    throw new Error(`Command injection prevention: Binary '${cmd}' is not whitelisted.`);
  }

  // 2. Argument Validation (prevent tricky flags if needed, though spawn without shell mitigates most)
  for (const arg of args) {
    if (arg.includes('&') || arg.includes('|') || arg.includes(';') || arg.includes('>')) {
      throw new Error(`Command injection prevention: Invalid characters in argument '${arg}'.`);
    }
  }

  return new Promise((resolve, reject) => {
    let stdout = '';
    let stderr = '';

    // 3. Execution without shell
    const child = spawn(cmd, args, {
      shell: false,
      timeout: timeoutMs
    });

    child.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    child.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    child.on('error', (err) => {
      reject(new Error(`Failed to start command: ${err.message}`));
    });

    child.on('close', (code) => {
      resolve({
        stdout: stdout.trim(),
        stderr: stderr.trim(),
        exitCode: code
      });
    });
  });
}
