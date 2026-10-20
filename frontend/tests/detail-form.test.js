import test from 'node:test'
import assert from 'node:assert/strict'
import { createDetailForm } from '../src/detail-form.js'

test('reopening an item restores every saved review field independently of attribution notes', () => {
  const detail = {
    tags: ['召回失败'], note: '归因说明',
    human_review: {
      accuracy: 1, completeness: 5, refused: true, unsupported: true,
      factually_incorrect: true, reviewer: '测试核验人', note: '评分说明',
    },
  }
  const form = createDetailForm(detail)
  assert.deepEqual(form, {
    tags: ['召回失败'], note: '归因说明', accuracy: 1, completeness: 5,
    refused: true, unsupported: true, factually_incorrect: true,
    reviewer: '测试核验人', review_note: '评分说明',
  })
  form.tags.push('排序问题')
  assert.deepEqual(detail.tags, ['召回失败'])
})

test('a saved negative factual-error judgment remains false rather than becoming unknown', () => {
  const form = createDetailForm({
    tags: [], note: '',
    human_review: { accuracy: 5, completeness: 4, refused: false, unsupported: false,
      factually_incorrect: false, reviewer: '测试核验人', note: '' },
  })
  assert.equal(form.factually_incorrect, false)
  assert.equal(form.refused, false)
  assert.equal(form.unsupported, false)
})

test('an unreviewed item uses defaults without leaking the previously opened review', () => {
  createDetailForm({ tags: [], note: '', human_review: {
    accuracy: 5, completeness: 5, reviewer: '上一题核验人', note: '上一题说明',
  } })
  assert.deepEqual(createDetailForm({ tags: [], note: '', human_review: null }), {
    tags: [], note: '', accuracy: 3, completeness: 3, refused: false,
    unsupported: false, factually_incorrect: null, reviewer: '', review_note: '',
  })
})
