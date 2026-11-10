"""Constructor-only checks: no model, payment or network request is made."""
import inspect
import unittest

from crashcart.investigator import Investigation, OpenAIModel, StructuredModel
from crashcart.model_transport import MODAL_MODEL, MODAL_ORIGIN


class ModelNamingTests(unittest.TestCase):
    @staticmethod
    def no_request(*args, **kwargs):
        raise AssertionError("Constructor must not send a request")

    def test_old_name_is_exact_alias_and_default_factory_is_shared_class(self):
        self.assertIs(OpenAIModel, StructuredModel)
        default = inspect.signature(Investigation).parameters["model_factory"].default
        self.assertIs(default, StructuredModel)

    def test_omitted_provider_still_selects_openai_responses(self):
        for model_class in (StructuredModel, OpenAIModel):
            model = model_class(environ={}, transport=self.no_request)
            self.assertEqual(model.config.provider, "openai")
            self.assertEqual(model.config.protocol, "responses")
            self.assertEqual(model.config.endpoint, "https://api.openai.com/v1/responses")
            self.assertEqual(model.evidence_mode, "LOCAL_TEST")

    def test_explicit_modal_keeps_existing_pinned_model_and_protocol(self):
        model = StructuredModel(environ={"CRASHCART_MODEL_PROVIDER": "modal"}, transport=self.no_request)
        self.assertEqual(model.config.provider, "modal")
        self.assertEqual(model.config.model, MODAL_MODEL)
        self.assertEqual(model.config.endpoint, MODAL_ORIGIN + "/v1/chat/completions")
        self.assertIs(type(model), OpenAIModel)


if __name__ == "__main__":
    unittest.main()
