"""OpenAI Responses API を使う ACC 向けアダプタ。"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from typing import Any

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    OpenAIError,
)

from acc.domain.entities.artifact import Artifact
from acc.domain.entities.interaction import AgentDecision, TurnInteractionSignal
from acc.domain.value_objects.ccs import CompressedCognitiveState
from acc.ports.outbound.agent_policy_port import AgentPolicyPort
from acc.ports.outbound.cognitive_compressor_model_port import CognitiveCompressorModelPort

_DEFAULT_MODEL = "gpt-4.1-mini"


class OpenAIConfigurationError(RuntimeError):
    """OpenAI 設定不備を表す例外。"""


class OpenAIResponseFormatError(RuntimeError):
    """OpenAI 応答フォーマット不正を表す例外。"""


class OpenAIRequestError(RuntimeError):
    """OpenAI API 呼び出し失敗を表す例外。"""


class _OpenAIResponsesBase:
    """Responses API 呼び出しの共通処理。"""

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.2,
        max_output_tokens: int = 1000,
    ) -> None:
        """モデル設定と呼び出しパラメータを初期化する。"""
        self._model: str = model if model is not None else os.getenv("OPENAI_MODEL", _DEFAULT_MODEL)
        self._api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        self._client: OpenAI | None = None

    def _get_client(self) -> OpenAI:
        if self._client is None:
            if not self._api_key:
                raise OpenAIConfigurationError("OPENAI_API_KEY が設定されていません。")
            self._client = OpenAI(api_key=self._api_key)
        return self._client

    def _request_text(self, *, instructions: str, prompt: str) -> str:
        try:
            response = self._get_client().responses.create(
                model=self._model,
                instructions=instructions,
                input=prompt,
                temperature=self._temperature,
                max_output_tokens=self._max_output_tokens,
            )
        except AuthenticationError as exc:
            raise OpenAIConfigurationError(
                "OpenAI 認証に失敗しました。OPENAI_API_KEY を確認してください。"
            ) from exc
        except (APITimeoutError, APIConnectionError, APIError, OpenAIError) as exc:
            raise OpenAIRequestError(
                f"OpenAI API 呼び出しに失敗しました: {exc.__class__.__name__}"
            ) from exc
        output_text = getattr(response, "output_text", None)
        if not isinstance(output_text, str):
            raise OpenAIResponseFormatError("OpenAI 応答に output_text が含まれていません。")
        normalized_text = output_text.strip()
        if not normalized_text:
            raise OpenAIResponseFormatError("OpenAI 応答テキストが空です。")
        return normalized_text


class OpenAICognitiveCompressorModelAdapter(
    _OpenAIResponsesBase,
    CognitiveCompressorModelPort,
):
    """CCS payload を OpenAI で生成する CCM アダプタ。"""

    def generate_next_state_payload(
        self,
        interaction_signal: TurnInteractionSignal,
        committed_state: CompressedCognitiveState,
        qualified_artifacts: Sequence[Artifact],
    ) -> Mapping[str, object]:
        """CCS スキーマ準拠 JSON payload を返す。"""
        instructions = (
            "あなたは ACC の Cognitive Compressor Model です。"
            " 有効な JSON object のみを返してください。Markdown フェンスは禁止です。"
            " Required keys: episodic_trace, semantic_gist, focal_entities, relational_map,"
            " goal_orientation, constraints, predictive_cue, uncertainty_signal, retrieved_artifacts."
            " 配列フィールドは空文字を含まない文字列配列にしてください。"
            " CCS の自然言語フィールドは日本語で記述してください。"
            " ホスト名・ID・製品名など識別子は原文を保持して構いません。"
            " 状態は簡潔かつ意思決定に必要な情報へ圧縮してください。"
        )
        prompt = _build_compressor_prompt(
            interaction_signal=interaction_signal,
            committed_state=committed_state,
            qualified_artifacts=qualified_artifacts,
        )
        response_text = self._request_text(instructions=instructions, prompt=prompt)
        payload = _parse_json_object(response_text)
        if not isinstance(payload, dict):
            raise OpenAIResponseFormatError("CCS payload が JSON object ではありません。")
        return payload


class OpenAIAgentPolicyAdapter(_OpenAIResponsesBase, AgentPolicyPort):
    """コミット済み CCS からユーザー応答を OpenAI で生成する。"""

    def decide(
        self,
        committed_state: CompressedCognitiveState,
        role: str,
        tools: Sequence[str],
    ) -> AgentDecision:
        """CCS と役割情報を使って応答文を返す。"""
        instructions = (
            "You are an operational assistant."
            " Follow the constraints in the provided cognitive state."
            " If uncertainty is high, state uncertainty explicitly."
            " Be concise and actionable."
        )
        prompt = _build_policy_prompt(
            committed_state=committed_state,
            role=role,
            tools=tools,
        )
        response_text = self._request_text(instructions=instructions, prompt=prompt)
        return AgentDecision(response=response_text, tool_actions=())


def _build_compressor_prompt(
    *,
    interaction_signal: TurnInteractionSignal,
    committed_state: CompressedCognitiveState,
    qualified_artifacts: Sequence[Artifact],
) -> str:
    committed_state_dict = asdict(committed_state)
    artifacts_payload = [
        {
            "artifact_id": artifact.artifact_id,
            "source": artifact.source,
            "content": artifact.content,
        }
        for artifact in qualified_artifacts
    ]

    prompt_payload: dict[str, Any] = {
        "interaction_signal": {
            "turn_id": interaction_signal.turn_id,
            "user_input": interaction_signal.user_input,
            "new_facts": list(interaction_signal.new_facts),
            "focus_entities": list(interaction_signal.focus_entities),
            "active_goal": interaction_signal.active_goal,
            "active_constraints": list(interaction_signal.active_constraints),
            "expected_next_steps": list(interaction_signal.expected_next_steps),
        },
        "previous_committed_state": committed_state_dict,
        "qualified_artifacts": artifacts_payload,
    }

    return (
        "次の入力 JSON をもとに ACC の次状態を更新してください。\n"
        "入力:\n"
        f"{json.dumps(prompt_payload, ensure_ascii=False)}\n"
        "出力は次の CCS を表す JSON object のみを返してください。"
    )


def _build_policy_prompt(
    *,
    committed_state: CompressedCognitiveState,
    role: str,
    tools: Sequence[str],
) -> str:
    payload = {
        "role": role,
        "tools": list(tools),
        "committed_state": asdict(committed_state),
    }
    return (
        "Generate the assistant reply for the latest user query using this context JSON:\n"
        f"{json.dumps(payload, ensure_ascii=False)}\n"
        "Focus on goal and constraints."
    )


def _parse_json_object(response_text: str) -> dict[str, object]:
    """モデル応答文字列から JSON object を抽出する。"""
    text = response_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise OpenAIResponseFormatError("CCS payload JSON のパースに失敗しました。") from exc

    if not isinstance(parsed, dict):
        raise OpenAIResponseFormatError("CCS payload が JSON object ではありません。")
    return parsed
