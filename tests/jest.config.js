// Jest 测试配置
module.exports = {
  // 测试环境
  testEnvironment: 'node',
  
  // 测试文件匹配
  testMatch: [
    '**/tests/**/*.test.js',
    '**/tests/**/*.test.ts',
    '**/__tests__/**/*.js',
    '**/__tests__/**/*.ts'
  ],
  
  // 文件扩展名
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json'],
  
  // 转换配置
  transform: {
    '^.+\\.tsx?$': 'ts-jest'
  },
  
  // 覆盖率配置
  collectCoverageFrom: [
    'src/**/*.{js,ts}',
    '!src/**/*.d.ts',
    '!src/**/__tests__/**'
  ],
  
  coverageDirectory: 'coverage',
  
  // 覆盖率阈值
  coverageThreshold: {
    global: {
      branches: 75,
      functions: 85,
      lines: 80,
      statements: 80
    }
  },
  
  // 覆盖率报告
  coverageReporters: ['text', 'lcov', 'html'],
  
  // 详细输出
  verbose: true,
  
  // 超时配置
  testTimeout: 10000,
  
  // 并发执行
  maxWorkers: '50%'
};
