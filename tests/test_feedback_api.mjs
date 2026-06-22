import assert from "node:assert";
import { validateFeedback, buildEmail } from "../wisprlitevercel/api/feedback.js";

// honeypot -> drop
assert.deepEqual(validateFeedback({ website: "x", message: "hi" }), { drop: true });
// empty message -> error
assert.equal(validateFeedback({ message: " " }).error, "empty_message");
// valid: trims, normalizes unknown category to "other", drops a bad email (doesn't reject)
const v = validateFeedback({ message: "  it crashed  ", category: "ZZZ", email: "nope", app_version: "2.26.0", os: "Win11" });
assert.equal(v.ok, true); assert.equal(v.message, "it crashed"); assert.equal(v.category, "other");
assert.equal(v.email, ""); assert.equal(v.appVersion, "2.26.0"); assert.equal(v.os, "Win11");
// known category kept; good email lowercased + reply_to set; subject + to correct
const v2 = validateFeedback({ message: "add dark mode", category: "idea", email: "A@B.com" });
assert.equal(v2.category, "idea"); assert.equal(v2.email, "a@b.com");
const mail = buildEmail(v2, "james@powleads.com", "PipeVoice <onboarding@resend.dev>");
assert.equal(mail.reply_to, "a@b.com"); assert.deepEqual(mail.to, ["james@powleads.com"]);
assert.ok(mail.subject.startsWith("[PipeVoice · idea]")); assert.ok(mail.text.includes("add dark mode"));
// message length cap
assert.equal(validateFeedback({ message: "x".repeat(9000) }).message.length, 5000);
console.log("OK");
