/**
 * Test cases for errorHandler utility
 * Run with: node errorHandler.test.js
 */

const { extractErrorMessage } = require('./errorHandler');

// Mock console.error
console.error = () => {};

const testCases = [
  {
    name: 'Simple string detail',
    error: {
      response: {
        data: {
          detail: 'Bid amount too low'
        }
      }
    },
    expected: 'Bid amount too low'
  },
  {
    name: 'Pydantic validation error (array)',
    error: {
      response: {
        data: {
          detail: [
            { type: 'value_error', loc: ['body', 'amount'], msg: 'Amount must be positive', input: -10 },
            { type: 'value_error', loc: ['body', 'bid_type'], msg: 'Invalid bid type', input: 'invalid' }
          ]
        }
      }
    },
    expected: 'body.amount: Amount must be positive, body.bid_type: Invalid bid type'
  },
  {
    name: 'Single error object',
    error: {
      response: {
        data: {
          detail: {
            type: 'value_error',
            loc: ['body', 'amount'],
            msg: 'Amount must be higher than current price',
            input: 100,
            url: 'https://errors.pydantic.dev/2.5/v/value_error'
          }
        }
      }
    },
    expected: 'body.amount: Amount must be higher than current price'
  },
  {
    name: 'Network error (no response)',
    error: {
      message: 'Network Error'
    },
    expected: 'Network error. Please check your connection.'
  },
  {
    name: 'Generic error object',
    error: {
      response: {
        data: {
          detail: { code: 'INVALID_BID', message: 'Invalid bid placement' }
        }
      }
    },
    expected: '{"code":"INVALID_BID","message":"Invalid bid placement"}'
  }
];

console.log('🧪 Running errorHandler tests...\n');

let passed = 0;
let failed = 0;

testCases.forEach((test, index) => {
  const result = extractErrorMessage(test.error);
  const success = result === test.expected;
  
  if (success) {
    console.log(`✅ Test ${index + 1}: ${test.name}`);
    passed++;
  } else {
    console.log(`❌ Test ${index + 1}: ${test.name}`);
    console.log(`   Expected: "${test.expected}"`);
    console.log(`   Got: "${result}"`);
    failed++;
  }
});

console.log(`\n📊 Results: ${passed} passed, ${failed} failed`);

if (failed === 0) {
  console.log('🎉 All tests passed!');
  process.exit(0);
} else {
  console.log('❌ Some tests failed');
  process.exit(1);
}
