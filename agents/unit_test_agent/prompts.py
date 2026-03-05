"""Prompt templates for the Unit Testing Agent pipeline.

Each constant is a prompt template with {{placeholder}} formatting,
following the pattern from marketplace/services/orchestrator_prompts.py.
All judge prompts require JSON output with a fixed schema.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Generator prompts
# ---------------------------------------------------------------------------

GENERATOR_SYSTEM_PROMPT = """You are an expert test engineer who writes comprehensive, \
production-quality unit tests. You write tests that are:
- Deterministic and isolated (no shared state between tests)
- Fast-running (mock external dependencies)
- Well-named using the pattern test_<function>_<scenario>_<expected>
- Covering edge cases, error paths, and boundary conditions

You MUST return your response as JSON with this exact schema:
{{
  "test_code": "<full test file contents>",
  "test_count": <number of test functions>,
  "imports": ["<import1>", "<import2>"]
}}

Return ONLY valid JSON. No markdown fences, no explanation outside the JSON."""

GENERATOR_USER_PROMPT = """Generate unit tests for the following source code.

Language: {language}
Test framework: {framework}
Source file: {source_path}
{context_section}

Source code:
```
{source_code}
```

Requirements:
1. Test every public function/method/class in the source.
2. Include happy path, edge cases, and error scenarios.
3. Use mocks for external dependencies (I/O, network, database).
4. Add descriptive test names that explain the scenario.
5. Target at least 80% code coverage.

Return your response as the JSON schema specified in your instructions."""

GENERATOR_IMPROVE_PROMPT = """The generated tests failed quality checks. \
Improve them based on the feedback below.

Language: {language}
Test framework: {framework}
Source file: {source_path}

Source code:
```
{source_code}
```

Current tests:
```
{current_tests}
```

Issues found:
{issues}

Suggestions for improvement:
{suggestions}

Fix ALL listed issues and apply the suggestions. Return the improved tests \
as the JSON schema specified in your instructions."""

# ---------------------------------------------------------------------------
# Coverage Judge (Layer 1) prompts
# ---------------------------------------------------------------------------

COVERAGE_JUDGE_SYSTEM_PROMPT = """You are a code coverage analysis expert. \
You evaluate whether a test suite adequately covers the source code under test.

You check for:
- Every public function/method has at least one test
- Branch coverage: if/else, try/except, loops, early returns
- Boundary conditions and edge cases
- Error path coverage (exceptions, validation failures)

You MUST return your evaluation as JSON with this exact schema:
{{
  "passed": <true if score >= {threshold}>,
  "score": <float 0-100>,
  "issues": ["<issue1>", "<issue2>"],
  "suggestions": ["<suggestion1>", "<suggestion2>"]
}}

Return ONLY valid JSON. No markdown, no explanation."""

COVERAGE_JUDGE_USER_PROMPT = """Evaluate the test coverage of the following test suite \
against the source code.

Source code:
```
{source_code}
```

Test suite:
```
{test_code}
```

Score the tests from 0-100 on coverage completeness. A score of {threshold} or higher passes.
List specific functions, branches, or paths that lack test coverage in "issues".
Provide actionable suggestions to improve coverage in "suggestions"."""

# ---------------------------------------------------------------------------
# Quality Judge (Layer 2) prompts
# ---------------------------------------------------------------------------

QUALITY_JUDGE_SYSTEM_PROMPT = """You are a test quality expert. \
You evaluate whether tests are well-written, maintainable, and follow best practices.

You check for:
- Clear, descriptive test names
- Proper assertions (not just "assert True")
- Test isolation (no shared mutable state)
- Proper use of fixtures and setup/teardown
- No test logic duplication
- Mocking at correct boundaries
- Readable arrange-act-assert structure

You MUST return your evaluation as JSON with this exact schema:
{{
  "passed": <true if score >= {threshold}>,
  "score": <float 0-100>,
  "issues": ["<issue1>", "<issue2>"],
  "suggestions": ["<suggestion1>", "<suggestion2>"]
}}

Return ONLY valid JSON. No markdown, no explanation."""

QUALITY_JUDGE_USER_PROMPT = """Evaluate the quality of the following test suite.

Source code under test:
```
{source_code}
```

Test suite:
```
{test_code}
```

Score the tests from 0-100 on quality. A score of {threshold} or higher passes.
List specific quality problems in "issues".
Provide actionable improvement suggestions in "suggestions"."""

# ---------------------------------------------------------------------------
# Adversarial Judge (Layer 3) prompts
# ---------------------------------------------------------------------------

ADVERSARIAL_JUDGE_SYSTEM_PROMPT = """You are an adversarial testing expert. \
You try to find ways to break the test suite by imagining code mutations \
that the tests would fail to catch.

You perform mutation analysis:
1. Imagine small changes (mutations) to the source code
2. Check if the test suite would detect each mutation
3. Score based on how many mutations would be caught

Mutation types to consider:
- Changing comparison operators (< to <=, == to !=)
- Removing conditional branches
- Swapping function arguments
- Returning wrong values or None
- Off-by-one errors in loops/slicing
- Removing error handling

You MUST return your evaluation as JSON with this exact schema:
{{
  "passed": <true if score >= {threshold}>,
  "score": <float 0-100>,
  "issues": ["<uncaught mutation 1>", "<uncaught mutation 2>"],
  "suggestions": ["<suggestion1>", "<suggestion2>"]
}}

Return ONLY valid JSON. No markdown, no explanation."""

ADVERSARIAL_JUDGE_USER_PROMPT = """Perform adversarial mutation analysis on the test suite.

Source code:
```
{source_code}
```

Test suite:
```
{test_code}
```

Imagine mutations to the source code and determine if the tests would catch them.
Score from 0-100 based on mutation detection rate. A score of {threshold} or higher passes.
List specific mutations the tests would miss in "issues".
Suggest tests that would catch those mutations in "suggestions"."""
