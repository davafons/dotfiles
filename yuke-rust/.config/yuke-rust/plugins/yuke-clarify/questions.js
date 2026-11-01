/** @typedef {{ label: string, description: string, recommended: boolean }} Choice */
/** @typedef {{ title: string, question: string, context: string, options: Choice[], multi_select: boolean }} Question */
/** @typedef {{ text: string, selected: number, other: boolean, checked?: number[], otherSelected?: boolean, notes?: boolean, committed?: boolean, responses?: string[] }} Draft */
/** @typedef {Question & { id: string, session: string, status: string, draft: Draft, token?: string, answer?: string, kind?: string, error?: string, responses?: string[], question_id?: string, batch_id?: string, batch_size?: number, batch_index?: number }} Entry */
/** @typedef {{ id: string, session: string, status: string, questions: Entry[], answers?: Record<string, { answers: string[] }>, token?: string }} Batch */

/** @param {unknown} value @param {string} name @param {number} max */
function requiredText(value, name, max) {
  if (
    typeof value !== "string" ||
    !value.trim() ||
    value.length > max ||
    /[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/u.test(value)
  ) {
    throw new Error(`${name} must be nonempty text of at most ${max} characters without control codes`);
  }
  return value.trim();
}

/** Validate model arguments before persisting anything. @param {unknown} args @returns {Question} */
export function validateQuestion(args) {
  if (!args || typeof args !== "object" || Array.isArray(args)) throw new Error("question arguments must be an object");
  const value = /** @type {Record<string, unknown>} */ (args);
  if (Object.keys(value).some((key) => !["title", "question", "context", "options", "multi_select"].includes(key)))
    throw new Error("unknown question field");
  if (value.multi_select !== undefined && typeof value.multi_select !== "boolean")
    throw new Error("multi_select must be boolean");
  const title = requiredText(value.title, "title", 120);
  const question = requiredText(value.question, "question", 4000);
  const context =
    value.context === undefined || value.context === "" ? "" : requiredText(value.context, "context", 4000);
  if (value.options !== undefined && (!Array.isArray(value.options) || value.options.length > 8))
    throw new Error("options must be an array of at most 8 choices");
  const options = /** @type {unknown[]} */ (value.options ?? []).map((option) => {
    if (!option || typeof option !== "object" || Array.isArray(option))
      throw new Error("each option must be an object");
    const choice = /** @type {Record<string, unknown>} */ (option);
    if (Object.keys(choice).some((key) => !["label", "description", "recommended"].includes(key)))
      throw new Error("unknown option field");
    if (choice.recommended !== undefined && typeof choice.recommended !== "boolean")
      throw new Error("recommended must be boolean");
    return {
      label: requiredText(choice.label, "option label", 120),
      description:
        choice.description === undefined || choice.description === ""
          ? ""
          : requiredText(choice.description, "option description", 500),
      recommended: choice.recommended === true,
    };
  });
  if (new Set(options.map((choice) => choice.label)).size !== options.length)
    throw new Error("option labels must be unique");
  if (options.filter((choice) => choice.recommended).length > 1) throw new Error("only one option can be recommended");
  if (value.multi_select === true && !options.length) throw new Error("multi_select requires options");
  return { title, question, context, options, multi_select: value.multi_select === true };
}

/** @param {unknown} args @returns {(Question & { question_id: string })[]} */
export function validateBatch(args) {
  if (!args || typeof args !== "object" || Array.isArray(args)) throw new Error("batch arguments must be an object");
  const value = /** @type {Record<string, unknown>} */ (args);
  if (Object.keys(value).some((key) => key !== "questions")) throw new Error("unknown batch field");
  if (!Array.isArray(value.questions) || value.questions.length < 1 || value.questions.length > 3)
    throw new Error("provide one to three questions");
  const questions = value.questions.map((raw) => {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) throw new Error("each question must be an object");
    const item = /** @type {Record<string, unknown>} */ (raw);
    if (
      Object.keys(item).some((key) => !["id", "header", "question", "context", "options", "multi_select"].includes(key))
    )
      throw new Error("unknown batch question field");
    const id = requiredText(item.id, "question id", 64);
    if (!/^[a-z][a-z0-9_]*$/u.test(id)) throw new Error("question ids must be snake_case");
    const header = requiredText(item.header, "header", 12);
    const options = Array.isArray(item.options)
      ? item.options.map((option) => {
          if (!option || typeof option !== "object" || Array.isArray(option)) return option;
          const choice = /** @type {Record<string, unknown>} */ (option);
          const label = typeof choice.label === "string" ? choice.label : "";
          return /\s*\(recommended\)$/iu.test(label)
            ? { ...choice, label: label.replace(/\s*\(recommended\)$/iu, ""), recommended: true }
            : choice;
        })
      : item.options;
    return {
      ...validateQuestion({
        title: header,
        question: item.question,
        ...(item.context !== undefined ? { context: item.context } : {}),
        ...(options !== undefined ? { options } : {}),
        ...(item.multi_select !== undefined ? { multi_select: item.multi_select } : {}),
      }),
      question_id: id,
    };
  });
  if (new Set(questions.map((question) => question.question_id)).size !== questions.length)
    throw new Error("question ids must be unique");
  return questions;
}

/** @param {Batch} batch */
export function batchAnswerMessage(batch) {
  const summary = batch.questions
    .map((question) =>
      [
        `${question.question_id}: ${question.question}`,
        ...(question.context ? [`Context: ${question.context}`] : []),
        (batch.answers?.[question.question_id ?? question.id]?.answers ?? []).join("; ") ||
          "Unanswered / skipped (not approval)",
      ].join("\n"),
    )
    .join("\n\n");
  return `[yuke-clarify ${batch.id}: answered]\n\n${summary}\n\nStructured answers:\n${JSON.stringify({ answers: batch.answers })}\n\nEmpty answer arrays are unanswered or explicitly skipped, NOT approval. Leave work dependent on those unanswered questions blocked.`;
}

/** The answer is user-authored content, with an unambiguous correlation ID. @param {Entry} entry */
export function answerMessage(entry) {
  return [
    `[yuke-clarify ${entry.id}: ${entry.kind}]`,
    `Title: ${entry.title}`,
    `Question: ${entry.question}`,
    ...(entry.context ? [`Context: ${entry.context}`] : []),
    entry.kind === "dismissed"
      ? "The user declined to answer. Do not treat this as approval or choose a default. Leave dependent work blocked."
      : `User answer: ${entry.answer}`,
    ...(entry.responses?.length ? [`Structured answers: ${JSON.stringify({ answers: entry.responses })}`] : []),
  ].join("\n\n");
}
