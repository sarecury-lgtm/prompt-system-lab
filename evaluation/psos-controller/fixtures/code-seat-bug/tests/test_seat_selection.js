"use strict";

const assert = require("node:assert/strict");
const { toggleSeat } = require("../src/seat_selection");

const original = ["A1"];
assert.deepEqual(toggleSeat([], "A1"), ["A1"]);
assert.deepEqual(toggleSeat(original, "B2"), ["A1", "B2"]);
assert.deepEqual(toggleSeat(["A1"], "A1"), []);
assert.deepEqual(original, ["A1"], "input array must not be mutated");

console.log("seat selection tests: PASS");
