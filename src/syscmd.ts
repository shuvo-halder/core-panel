import { spawn } from 'child_process';

/**
 * Securely executes a system command.
 * By using `spawn` without `shell: true`, we prevent shell injection vulnerabilities (RCE).
 * 
 * @param command The executable to run (e.g., 'ls', 'systemctl')
 * @param args Array of arguments (e.g., ['-l', '/var/www'])
 * @returns Promise resolving to the command output
 */
export async function runSafeCommand(command: string, args: string[] = []): Promise<string> {
  return new Promise((resolve, reject) => {
    // SECURITY: shell: false is the default for spawn, explicitly ensuring it here.
    // This prevents operators like `&&`, `;`, `|` from being evaluated by the shell.
    const proc = spawn(command, args, { shell: false });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(`Command failed with exit code ${code}: ${stderr}`));
      } else {
        resolve(stdout.trim());
      }
    });

    proc.on('error', (err) => {
      reject(new Error(`Failed to start command: ${err.message}`));
    });
  });
}
