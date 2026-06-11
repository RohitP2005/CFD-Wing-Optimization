#!/usr/bin/env node

/**
 * Frontend Setup Verification Script
 * Checks if all dependencies and configurations are correct
 */

const fs = require('fs');
const path = require('path');

const colors = {
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  reset: '\x1b[0m',
};

const checks = [];

function check(name, condition, details = '') {
  const status = condition ? `${colors.green}✓${colors.reset}` : `${colors.red}✗${colors.reset}`;
  console.log(`${status} ${name}${details ? ` — ${details}` : ''}`);
  checks.push({ name, passed: condition });
}

console.log(`${colors.blue}=== Wing Design Frontend Setup Verification ===${colors.reset}\n`);

// 1. Check Node.js
const nodeVersion = process.version;
const nodeMajor = parseInt(nodeVersion.split('.')[0].substring(1));
check('Node.js version', nodeMajor >= 16, `Found: ${nodeVersion}`);

// 2. Check package.json exists
const pkgPath = path.join(__dirname, 'package.json');
check('package.json exists', fs.existsSync(pkgPath));

// 3. Check node_modules installed
const nodeModulesPath = path.join(__dirname, 'node_modules');
check('Dependencies installed', fs.existsSync(nodeModulesPath), fs.existsSync(nodeModulesPath) ? 'node_modules/ found' : 'Run: npm install');

// 4. Check key dependencies
const packages = ['react', '@tanstack/react-router', '@tanstack/react-query', 'recharts', 'zod'];
packages.forEach(pkg => {
  const pkgPath = path.join(__dirname, 'node_modules', pkg);
  check(`  ${pkg} installed`, fs.existsSync(pkgPath));
});

// 5. Check source files
check('src/ directory exists', fs.existsSync(path.join(__dirname, 'src')));
check('src/lib/api.ts exists', fs.existsSync(path.join(__dirname, 'src/lib/api.ts')));
check('src/routes/ exists', fs.existsSync(path.join(__dirname, 'src/routes')));

// 6. Check config files
check('vite.config.ts exists', fs.existsSync(path.join(__dirname, 'vite.config.ts')));
check('tsconfig.json exists', fs.existsSync(path.join(__dirname, 'tsconfig.json')));

// 7. Check .env configuration
const envPath = path.join(__dirname, '.env');
const envExists = fs.existsSync(envPath);
check('.env file exists', envExists, envExists ? '(optional but recommended)' : 'Copy from .env.example');

if (envExists) {
  const envContent = fs.readFileSync(envPath, 'utf-8');
  const hasApiUrl = envContent.includes('VITE_API_BASE_URL');
  check('  VITE_API_BASE_URL configured', hasApiUrl);
}

// 8. Check build outputs
check('Vite build configured', fs.existsSync(path.join(__dirname, 'vite.config.ts')));

// 9. Summary
console.log(`\n${colors.blue}=== Summary ===${colors.reset}`);
const passed = checks.filter(c => c.passed).length;
const total = checks.length;
const percentage = Math.round((passed / total) * 100);

if (passed === total) {
  console.log(`${colors.green}✓ All checks passed! (${percentage}%)${colors.reset}`);
  console.log(`\nReady to run: ${colors.blue}npm run dev${colors.reset}`);
} else {
  console.log(`${colors.yellow}⚠ ${total - passed} check(s) failed (${percentage}%)${colors.reset}`);
  console.log(`\nFailing checks:`);
  checks.filter(c => !c.passed).forEach(c => {
    console.log(`  - ${c.name}`);
  });
  console.log(`\nTo fix: ${colors.blue}npm install${colors.reset}`);
}

// 10. Backend connectivity check
console.log(`\n${colors.blue}=== Backend Connectivity ===${colors.reset}`);
console.log(`Backend expected at: http://localhost:8000`);
console.log(`To test: ${colors.blue}curl http://localhost:8000/api/health${colors.reset}`);
console.log(`API docs: http://localhost:8000/docs`);

process.exit(passed === total ? 0 : 1);
