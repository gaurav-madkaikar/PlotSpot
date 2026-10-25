"""Reviewed local model artifacts; changing a tag requires an explicit digest update."""
DIGESTS = {
    'nomic-embed-text:v1.5': '0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f',
    'llama3.2:3b': 'a80c4f17acd55265feec403c7aef86be0c25983ab279d83f3bcd3abbcb5b8b72',
    'qwen3.5:9b': '6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7',
}


async def verify_local_model(client, model):
    response = await client.get('/api/tags')
    response.raise_for_status()
    records = response.json()['models']
    if not any(record.get('name') == model and record.get('digest') == DIGESTS.get(model) for record in records):
        raise ValueError('Local model is missing or its reviewed digest changed')
