import base64
import httpx
from urllib.parse import urlsplit
from app.config import get_settings
from app.ingestion.dpdpa_scrubber import scrub_text

DEMO_TRANSCRIPTS = {
    "spice-lab": "Lab screen of synthetic lot-MX-02 flags suspected ferbam residue. The creator requests accredited confirmation. Multi-city consumers report hives and itchy throat.",
    "honey-nmr": "Synthetic NMR screen alleges C3/C4 rice-syrup in honey from an unauthorized third-party seller. This creator claim is not an accredited confirmation.",
}


async def transcribe(
    audio: bytes | None,
    provider="sarvam",
    language="hi",
    demo_key: str | None = None,
    lawful_basis: str | None = None,
) -> dict:
    if demo_key:
        if demo_key not in DEMO_TRANSCRIPTS:
            raise ValueError("Unknown demo clip")
        return {
            "text": DEMO_TRANSCRIPTS[demo_key],
            "provider": "synthetic-transcript",
            "synthetic": True,
            "redacted_fields": [],
        }
    if not audio or len(audio) > 10_000_000:
        raise ValueError("Provide audio of at most 10 MB")
    if lawful_basis not in {"consent", "authorized_support_processing"}:
        raise ValueError("An explicit processing basis is required for private audio")
    settings = get_settings()
    async with httpx.AsyncClient(timeout=60) as client:
        if provider == "sarvam":
            if not settings.sarvam_api_key:
                raise LookupError("SARVAM_API_KEY is not configured")
            response = await client.post(
                "https://api.sarvam.ai/speech-to-text",
                headers={"api-subscription-key": settings.sarvam_api_key},
                data={
                    "model": "saaras:v3",
                    "mode": "transcribe",
                    "language_code": "unknown",
                },
                files={"file": ("input.wav", audio, "audio/wav")},
            )
            response.raise_for_status()
            text = response.json()["transcript"]
        elif provider == "bhashini":
            if not settings.bhashini_api_key or not settings.bhashini_user_id:
                raise LookupError("BHASHINI_API_KEY and BHASHINI_USER_ID are required")
            config = await client.post(
                "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline",
                headers={
                    "userID": settings.bhashini_user_id,
                    "ulcaApiKey": settings.bhashini_api_key,
                },
                json={
                    "pipelineTasks": [
                        {
                            "taskType": "asr",
                            "config": {"language": {"sourceLanguage": language}},
                        }
                    ],
                    "pipelineRequestConfig": {
                        "pipelineId": settings.bhashini_pipeline_id
                    },
                },
            )
            config.raise_for_status()
            data = config.json()
            endpoint = data["pipelineInferenceAPIEndPoint"]
            callback = endpoint["callbackUrl"]
            host = urlsplit(callback).hostname or ""
            if urlsplit(callback).scheme != "https" or not (
                host == "bhashini.gov.in" or host.endswith(".bhashini.gov.in")
            ):
                raise ValueError("Untrusted Bhashini inference callback")
            auth = endpoint["inferenceApiKey"]
            service = data["pipelineResponseConfig"][0]["config"][0]["serviceId"]
            response = await client.post(
                callback,
                headers={auth["name"]: auth["value"]},
                json={
                    "pipelineTasks": [
                        {
                            "taskType": "asr",
                            "config": {
                                "language": {"sourceLanguage": language},
                                "serviceId": service,
                                "audioFormat": "wav",
                                "samplingRate": 16000,
                            },
                        }
                    ],
                    "inputData": {
                        "audio": [{"audioContent": base64.b64encode(audio).decode()}]
                    },
                },
            )
            response.raise_for_status()
            text = response.json()["pipelineResponse"][0]["output"][0]["source"]
        else:
            raise ValueError("Unknown transcription provider")
    cleaned, fields = scrub_text(text)
    return {
        "text": cleaned,
        "provider": provider,
        "synthetic": False,
        "redacted_fields": fields,
    }
