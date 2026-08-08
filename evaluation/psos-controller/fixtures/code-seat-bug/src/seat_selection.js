"use strict";

function toggleSeat(selectedSeats, seatId) {
  if (!Array.isArray(selectedSeats)) {
    throw new TypeError("selectedSeats must be an array");
  }
  if (typeof seatId !== "string" || seatId.length === 0) {
    throw new TypeError("seatId must be a non-empty string");
  }

  const next = [...selectedSeats];
  if (!next.includes(seatId)) {
    next.push(seatId);
  }
  return next;
}

module.exports = { toggleSeat };
