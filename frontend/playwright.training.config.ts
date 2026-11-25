import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e/training", timeout: 90000, expect: {timeout:15000},
  fullyParallel:false, workers:1, retries:0,
  reporter:[["list"],["html",{outputFolder:"training-report",open:"never"}]],
  outputDir:"training-test-results",
  use:{baseURL:"http://127.0.0.1:3400",timezoneId:"Asia/Manila",trace:"retain-on-failure",screenshot:"only-on-failure",
    launchOptions:process.env.TRAINING_CHROMIUM_PATH?{executablePath:process.env.TRAINING_CHROMIUM_PATH}:{}},
  projects:[{name:"training-desktop",use:{...devices["Desktop Chrome"]}},{name:"training-mobile",use:{...devices["Pixel 7"]}}]
});
