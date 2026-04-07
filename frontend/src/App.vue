<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount , watch, nextTick } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const API_BASE_URL = '/api'
//const API_BASE_URL = 'http://localhost:5000/api'
// const API_URL = import.meta.env.VITE_API_URL
// const API_BASE_URL = `${API_URL}/api`
const chunkLimit = ref(1)
const isOpen = ref(false)
const userInput = ref('')
const isLoading = ref(false)
const loadingChat = ref(false)
const apiError = ref('')
const isCreateModalOpen = ref(false)
const isCreateChunkModalOpen = ref(false)
const isCreatePromptModalOpen = ref(false)
const isEditPromptModalOpen = ref(false)
const chunkSearch = ref('')
const showChunkDropdown = ref(false)
const isDeleteModalOpen = ref(false)
const isDeleteModalOpenChunk = ref(false)
const isSaving = ref(false)
const deleteTargetId = ref<string | null>(null)
const chatBody = ref<HTMLElement | null>(null)
const isLLMEnabled = ref(true) // mặc định bật
const showSettings = ref(false)
const settingsRef = ref<HTMLElement | null>(null)
// const sessionId = crypto.randomUUID()
const originalData = ref<any>(null)

const notedLogs = ref<Set<number>>(new Set())
const TENANT_STORAGE_KEY = 'selected_tenant_code'
const NULL_TENANT_CODE = 'quoc_gia'
const ALL_TENANTS_FILTER = '__all_tenants__'

function normalizeTenantCode(value: unknown) {
  return (value ?? '').toString().trim() || NULL_TENANT_CODE
}

function getStoredTenantCode() {
  const value = localStorage.getItem(TENANT_STORAGE_KEY)
  return value?.trim() || null
}

function requireSelectedTenant(actionLabel: string, showError = true) {
  const storedTenantCode = getStoredTenantCode()

  if (!selectedTenantCode.value || !storedTenantCode || storedTenantCode !== selectedTenantCode.value) {
    if (showError) {
      apiError.value = `Vui lòng chọn tenant trước khi ${actionLabel}`
    }
    return null
  }

  return storedTenantCode
}

marked.setOptions({
  breaks: true
})

function renderMarkdown(text: string) {
  const rawHtml = marked.parse(text || '') as string
  return DOMPurify.sanitize(rawHtml)
}

function toApiTenantCode(value: string | null | undefined) {
  if (!value || value === NULL_TENANT_CODE) {
    return null
  }

  return value
}


// đóng khi click ngoài
function handleClickOutside(event: MouseEvent) {
  if (
    settingsRef.value &&
    !settingsRef.value.contains(event.target as Node)
  ) {
    showSettings.value = false
  }
}

async function toggleNote(item: any) {
  try {
    const res = await fetch(`${API_BASE_URL}/toggle-note/${item.id}`, {
      method: 'POST'
    })

    const data = await res.json()

    if (data.success) {
      item.is_noted = data.is_noted
    }

  } catch (err) {
    console.error(err)
  }
}

watch(notedLogs, () => {
  localStorage.setItem(
    "noted_logs",
    JSON.stringify([...notedLogs.value])
  )
})

const logs = ref<{ type: string; message: string }[]>([])
const logBody = ref<HTMLElement | null>(null)

function addLog(message: string, type: 'info' | 'warn' | 'error' = 'info') {
  logs.value.push({
    type,
    message: `[${new Date().toLocaleTimeString()}] ${message}`
  })
}

function clearLogs() {
  logs.value = []
}

// Auto scroll xuống cuối khi có log mới
watch(logs, async () => {
  await nextTick()
  if (logBody.value) {
    logBody.value.scrollTop = logBody.value.scrollHeight
  }
}, { deep: true })


const logPanel = ref<HTMLElement | null>(null)

let isDragging = false
let offsetX = 0
let offsetY = 0

function startDrag(e: MouseEvent) {
  if (!logPanel.value) return

  isDragging = true
  const rect = logPanel.value.getBoundingClientRect()

  offsetX = e.clientX - rect.left
  offsetY = e.clientY - rect.top

  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
}

function onDrag(e: MouseEvent) {
  if (!isDragging || !logPanel.value) return

  logPanel.value.style.left = `${e.clientX - offsetX}px`
  logPanel.value.style.top = `${e.clientY - offsetY}px`
  logPanel.value.style.bottom = 'auto'
}

function stopDrag() {
  isDragging = false
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
}

const sortBy = ref<'text_content' | ''>('')      // hiện tại chỉ sort theo text_content
const sortDir = ref<'asc' | 'desc'>('asc')

function toggleSortText() {
  if (sortBy.value !== 'text_content') {
    sortBy.value = 'text_content'
    sortDir.value = 'asc'
  } else {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  }
}

const sortedFilteredChunks = computed(() => {
  const arr = [...filteredChunks.value] // copy để không mutate computed gốc
  if (sortBy.value !== 'text_content') return arr

  arr.sort((a, b) => {
    const A = (a.text_content ?? '').toString()
    const B = (b.text_content ?? '').toString()

    // so sánh tiếng Việt ổn hơn
    const cmp = A.localeCompare(B, 'vi', { sensitivity: 'base' })
    return sortDir.value === 'asc' ? cmp : -cmp
  })

  return arr
})



async function clearChat() {

  // xóa session cũ
  localStorage.removeItem("chat_session_id")

  // tạo session mới
  const newSessionId = crypto.randomUUID()
  localStorage.setItem("chat_session_id", newSessionId)

  // reset UI
  messages.value = [
    { text: 'Xin chào! Tôi là trợ lý AI của UBND Phường.', from: 'bot' }
  ]
}

const newAlias = ref({
  alias_text: '',
  normalized_alias: '',
  document_id: null
})

const newChunk = ref({
  tenant_code: localStorage.getItem(TENANT_STORAGE_KEY),
  scope: 'xa_phuong',
  text_content: '',
  procedure_name: null,
  category: null,
  subject: null,
  organization_unit: null
})

const newPrompt = ref({
  prompt_name: '',
  prompt_type: '',
  content: '',
  description: '',
  version: 1,
  is_active: true,
})

function openDeleteModal(id: string) {
  deleteTargetId.value = id
  isDeleteModalOpen.value = true
}

function openDeleteModalChunk(id: string) {
  deleteTargetId.value = id
  isDeleteModalOpenChunk.value = true
}

function closeDeleteModal() {
  deleteTargetId.value = null
  isDeleteModalOpen.value = false
  isDeleteModalOpenChunk.value = false
}

const filteredChunksForSelect = computed(() => {
  const tenantScopedChunks = selectedTenantCode.value
    ? chunksData.value.filter(chunk => normalizeTenantCode(chunk.tenant_code) === selectedTenantCode.value)
    : chunksData.value

  if (!chunkSearch.value) return tenantScopedChunks

  return tenantScopedChunks.filter(chunk =>
    chunk.text_content
      ?.toLowerCase()
      .includes(chunkSearch.value.toLowerCase())
  )
})

function highlightChunk(text: string) {
  if (!chunkSearch.value) return text

  const keyword = chunkSearch.value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const regex = new RegExp(`(${keyword})`, 'gi')

  return text.replace(regex, '<mark class="highlight">$1</mark>')
}

type ChatMessage = {
  text: string
  from: 'user' | 'bot'
  createdAt?: number
  thoughts?: string[]
  showThoughts?: boolean
  isThinking?: boolean
  currentThinking?: string
  chunks?: any[]
}

// chat messages shown in widget
const messages = ref<ChatMessage[]>([
  { text: 'Xin chào! Tôi là trợ lý AI của UBND Phường.', from: 'bot' }
])

const autoScrollOnIncoming = ref(true)
const AUTO_SCROLL_THRESHOLD_PX = 120
const showChunksModal = ref(false)
const selectedMessageChunks = ref<any[]>([])
const exactChunkIdFilter = ref('')

function getThinkingThought(msg: ChatMessage) {
  if (!msg.isThinking) return ''
  if (msg.currentThinking) return msg.currentThinking

  const thoughts = msg.thoughts ?? []
  return thoughts.length ? thoughts[thoughts.length - 1] : ''
}

function formatMessageTime(timestamp?: number) {
  if (!timestamp) return ''
  return new Date(timestamp).toLocaleTimeString('vi-VN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

function updateAutoScrollState() {
  if (!chatBody.value) return
  const el = chatBody.value
  const distanceToBottom = el.scrollHeight - el.scrollTop - el.clientHeight
  autoScrollOnIncoming.value = distanceToBottom <= AUTO_SCROLL_THRESHOLD_PX
}

function handleChatBodyScroll() {
  updateAutoScrollState()
}

function scrollToBottom() {
  if (chatBody.value) {
    chatBody.value.scrollTop = chatBody.value.scrollHeight
  }
}

watch(messages, async () => {
  await nextTick()
  if (autoScrollOnIncoming.value) {
    scrollToBottom()
  }
}, { deep: true })

function getSessionId() {
  let sessionId = localStorage.getItem("chat_session_id")

  if (!sessionId) {
    sessionId = crypto.randomUUID()
    localStorage.setItem("chat_session_id", sessionId)
  }

  return sessionId
}

function viewChunksFromMessage(chunks: any[]) {
  selectedMessageChunks.value = chunks
  showChunksModal.value = true
}

function filterChunkFromReference(chunk: any) {
  const chunkId = (chunk?.id ?? '').toString().trim()
  if (!chunkId) return

  exactChunkIdFilter.value = chunkId
  categoryFilter.value = ''
  subjectFilter.value = ''
  searchKeyword.value = ''

  showChunksModal.value = false
  activeSection.value = 'chunks'

  nextTick(() => {
    const row = document.getElementById(`chunk-row-${chunkId}`)
    if (row) {
      row.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  })
}

// async function sendMessage() {
//   if (!userInput.value.trim()) return

//   const tenantCode = requireSelectedTenant('gửi tin nhắn')
//   if (!tenantCode) return

//   const text = userInput.value.trim()
//   const sessionId = getSessionId()
//   // push user message
//   messages.value.push({ text, from: 'user' })
//   userInput.value = ''
  
//   // clear table data
//   responses.value = []
  
//   // switch to test section to show data-table
//   activeSection.value = 'test'
  
//   // call backend API
//   loadingChat.value = true
//   apiError.value = ''
//   clearLogs();
//   try {
//     const res = await fetch(`${API_BASE_URL}/chat-stream`, {
//       method: 'POST',
//       headers: { 'Content-Type': 'application/json' },
//       body: JSON.stringify({
//         message: text,
//         session_id: sessionId,
//         use_llm: isLLMEnabled.value,
//         chunk_limit: chunkLimit.value,
//         tenant_code: tenantCode,
//       })
//     })

//     const reader = res.body!.getReader()
//     const decoder = new TextDecoder()

//     while (true) {
//       const { done, value } = await reader.read()
//       if (done) break

//       const chunk = decoder.decode(value)
//       const lines = chunk.split('\n\n')

//       lines.forEach(line => {
//         if (line.startsWith('data: ')) {
//           const data = JSON.parse(line.replace('data: ', ''))

//           if (data.log) {
//             addLog(data.log)
//           }

//           if (data.chunks) {
//             let botReply = data.replies
//             messages.value.push({ text: botReply, from: 'bot' })
//             // update table with all returned responses
//             responses.value = data.chunks || []
//           }
//         }
//       })
//     }
//   } catch (error: any) {
//     apiError.value = `Connection error: ${error.message}`
//     messages.value.push({ text: 'Xin lỗi, có lỗi khi kết nối đến server.', from: 'bot' })
//   } finally {
//     loadingChat.value = false
//     loadLogs(true)
//   }
// }



// async function sendMessage_v1() {
//   if (!userInput.value.trim()) return

//   const tenantCode = requireSelectedTenant('gửi tin nhắn')
//   if (!tenantCode) return

//   const text = userInput.value.trim()
//   const sessionId = getSessionId()

//   messages.value.push({ text, from: 'user' })
//   userInput.value = ''
//   responses.value = []
//   activeSection.value = 'test'
//   loadingChat.value = true
//   apiError.value = ''
//   clearLogs()

//   try {
//     const res = await fetch(`${API_BASE_URL}/chat-stream`, {
//       method: 'POST',
//       headers: { 'Content-Type': 'application/json' },
//       body: JSON.stringify({
//         message: text,
//         session_id: sessionId,
//         use_llm: isLLMEnabled.value,
//         chunk_limit: chunkLimit.value,
//         tenant_code: tenantCode,
//       })
//     })

//     if (!res.ok) throw new Error(`HTTP ${res.status}`)
//     if (!res.body) throw new Error('Response body is empty')

//     const reader = res.body.getReader()
//     const decoder = new TextDecoder()

//     let buffer = ''
//     let botMessageIndex: number | null = null

//     while (true) {
//       const { done, value } = await reader.read()

//       if (done) {
//         buffer += decoder.decode()
//         break
//       }

//       buffer += decoder.decode(value, { stream: true })

//       const events = buffer.split('\n\n')
//       buffer = events.pop() || ''

//       for (const event of events) {
//         const line = event.trim()
//         if (!line.startsWith('data: ')) continue

//         try {
//           const data = JSON.parse(line.slice(6))

//           if (data.log) {
//             addLog(data.log)
//             continue
//           }

//           if ('token' in data) {
//             if (botMessageIndex === null) {
//               messages.value.push({ text: '', from: 'bot' })
//               botMessageIndex = messages.value.length - 1
//             }

//             if (botMessageIndex !== null) {
//               const botMessage = messages.value[botMessageIndex]
//               if (botMessage) {
//                 botMessage.text += String(data.token || '')
//               }
//             }

//             continue
//           }

//           if (data.done) {
//             responses.value = Array.isArray(data.chunks) ? data.chunks : []
//             botMessageIndex = null
//             continue
//           }

//           // kết quả final kiểu cũ / non-stream
//           if ('replies' in data) {
//             messages.value.push({ text: data.replies || '', from: 'bot' })
//             responses.value = Array.isArray(data.chunks) ? data.chunks : []
//             botMessageIndex = null
//             continue
//           }
//         } catch (err) {
//           console.error('Failed to parse SSE event:', event)
//         }
//       }
//     }
//   } catch (error: any) {
//     apiError.value = `Connection error: ${error.message}`
//     messages.value.push({
//       text: 'Xin lỗi, có lỗi khi kết nối đến server.',
//       from: 'bot'
//     })
//   } finally {
//     loadingChat.value = false
//     loadLogs(true)
//   }
// }


async function sendMessage() {
  if (!userInput.value.trim()) return

  const tenantCode = requireSelectedTenant('gửi tin nhắn')
  if (!tenantCode) return

  const text = userInput.value.trim()
  const sessionId = getSessionId()

  messages.value.push({ text, from: 'user', createdAt: Date.now() })
  messages.value.push({ text: '', from: 'bot', thoughts: [], showThoughts: false, isThinking: true, createdAt: Date.now() })
  userInput.value = ''
  responses.value = []
  activeSection.value = 'test'
  loadingChat.value = true
  apiError.value = ''
  let botMessageIndex: number | null = messages.value.length - 1

  try {
    clearLogs()
    const res = await fetch(`${API_BASE_URL}/chat-stream-v2`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: text,
        session_id: sessionId,
        tenant_code: tenantCode
      })
    })

    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    if (!res.body) throw new Error('Response body is empty')

    const reader = res.body.getReader()
    const decoder = new TextDecoder()

    let buffer = ''

    const processEvent = (event: string) => {
      const line = event.trim()
      if (!line.startsWith('data: ')) return

      try {
        const data = JSON.parse(line.slice(6))

        const ensureBotMessage = () => {
          if (botMessageIndex === null) {
            messages.value.push({ text: '', from: 'bot', thoughts: [], showThoughts: true, isThinking: true, createdAt: Date.now() })
            botMessageIndex = messages.value.length - 1
          }
          const idx = botMessageIndex as number
          return messages.value[idx]!
        }

        if (data.log) {
          addLog(data.log)
          return
        }

        if (data.thought) {
          const botMessage = ensureBotMessage()
          const thoughts = botMessage.thoughts ?? []
          const thoughtLines = String(data.thought)
            .split(/\r?\n/)
            .map(line => line.trim())
            .filter(Boolean)

          if (thoughtLines.length > 0) {
            thoughts.push(...thoughtLines)
            // Giữ câu suy nghĩ hiện tại, chỉ thay khi có log mới.
            botMessage.currentThinking = thoughtLines[thoughtLines.length - 1]
          }
          botMessage.thoughts = thoughts
          if (botMessage.isThinking !== false) {
            botMessage.showThoughts = true
          }
          return
        }

        if ('token' in data) {
          const botMessage = ensureBotMessage()
          if (botMessage) {
            botMessage.isThinking = false
            botMessage.showThoughts = false
            botMessage.text += String(data.token || '')
          }
          return
        }

        if (data.done) {
          if (botMessageIndex !== null) {
            const botMessage = messages.value[botMessageIndex]
            if (botMessage) {
              botMessage.isThinking = false
              botMessage.showThoughts = false
            }
          }
          botMessageIndex = null
          return
        }
      } catch (err) {
        console.error('Failed to parse SSE event:', event)
      }
    }

    while (true) {
      const { done, value } = await reader.read()

      if (done) {
        buffer += decoder.decode()
        break
      }

      buffer += decoder.decode(value, { stream: true })

      const events = buffer.split('\n\n')
      buffer = events.pop() || ''

      for (const event of events) {
        processEvent(event)
      }
    }

    // parse nốt phần còn sót lại
    if (buffer.trim()) {
      processEvent(buffer)
    }
  } catch (error: any) {
    if (botMessageIndex !== null) {
      const botMessage = messages.value[botMessageIndex]
      if (botMessage && botMessage.from === 'bot' && !botMessage.text && botMessage.isThinking) {
        messages.value.splice(botMessageIndex, 1)
      }
    }
    apiError.value = `Connection error: ${error.message}`
    messages.value.push({
      text: 'Xin lỗi, có lỗi khi kết nối đến server.',
      from: 'bot',
      createdAt: Date.now()
    })
  } finally {
    loadingChat.value = false
    loadLogs(true)
  }
}


// async function sendMessageNotStream() {
//   if (!userInput.value.trim()) return

//   const tenantCode = requireSelectedTenant('gửi tin nhắn')
//   if (!tenantCode) return

//   const text = userInput.value.trim()

//   messages.value.push({ text, from: 'user' })
//   userInput.value = ''
//   responses.value = []
//   activeSection.value = 'test'
//   const sessionId = getSessionId()

//   loadingChat.value = true
//   apiError.value = ''

//   try {
//     const response = await fetch(`${API_BASE_URL}/chat`, {
//       method: 'POST',
//       headers: { 'Content-Type': 'application/json' },
//       body: JSON.stringify({
//         message: text,
//         session_id: sessionId,
//         tenant_code: tenantCode,
//       })
//     })

//     if (!response.ok) {
//       const errData = await response.json().catch(() => ({}))
//       throw new Error(errData.error || `API error: ${response.status}`)
//     }

//     const data = await response.json()
//     const botReply = data.response?.response || 'Không có dữ liệu phản hồi.'

//     messages.value.push({ text: botReply, from: 'bot' })
//     responses.value = data.chunks || []
//   } catch (error: any) {
//     apiError.value = `Connection error: ${error.message}`
//     messages.value.push({ text: 'Xin lỗi, có lỗi khi kết nối đến server.', from: 'bot' })
//   } finally {
//     loadingChat.value = false
//     loadLogs(true)
//   }
// }

// async function sendMessage() {
//   if (!userInput.value.trim()) return
//   const text = userInput.value.trim()
//   // push user message
//   messages.value.push({ text, from: 'user' })
//   userInput.value = ''
  
//   // clear table data
//   responses.value = []
  
//   // switch to test section to show data-table
//   activeSection.value = 'test'
  
//   // call backend API
//   isLoading.value = true
//   isSaving.value = true
//   apiError.value = ''
  
//   try {
//     const response = await fetch(`${API_BASE_URL}/chat`, {
//       method: 'POST',
//       headers: { 'Content-Type': 'application/json' },
//       body: JSON.stringify({ message: text })
//     })
    
//     if (!response.ok) {
//       throw new Error(`API error: ${response.status}`)
//     }
    
//     const data = await response.json()
    
//     // display bot response in chat
//     if (data.replies && data.replies.length > 0) {
//       let botReply = data.replies[0].text_content
//       messages.value.push({ text: botReply, from: 'bot' })
//     }
    
//     // update table with all returned responses
//     responses.value = data.replies || []
//     addLog(data.log_data)
//   } catch (error: any) {
//     apiError.value = `Connection error: ${error.message}`
//     messages.value.push({ text: 'Xin lỗi, có lỗi khi kết nối đến server.', from: 'bot' })
//   } finally {
//     isLoading.value = false
//     isSaving.value = false
//   }
// }
const responses = ref<Array<{id: string; text_content: string; confidence_score: number}>>([])
const chunksData = ref<Array<any>>([])
const aliasData = ref<Array<any>>([])
const logsData = ref<Array<any>>([])
const promptsData = ref<Array<any>>([])
const tenantsData = ref<Array<any>>([])
const categoryFilter = ref<string>('')
const subjectFilter = ref<string>('')
const typeLogFilter = ref<string>('')
const editingId = ref<string | null>(null)
const editingData = ref<any>(null)
const promptEditingId = ref<string | null>(null)
const promptEditingData = ref<any>(null)
const activeSection = ref("tenants");
const searchKeyword = ref('')
const selectedTenantCode = ref(localStorage.getItem(TENANT_STORAGE_KEY))
const chunksTenantFilter = ref<string>(ALL_TENANTS_FILTER)
// const relationSourceChunkId = ref('')
// const relationSearchKeyword = ref('')
// const relationSelectedTargetIds = ref<string[]>([])
// const relationExistingTargetIds = ref<Set<string>>(new Set())
// const relationLoading = ref(false)

// const relationSourceOptions = computed(() => {
//   return chunksData.value.filter(item => normalizeTenantCode(item.tenant_code) === selectedTenantCode.value)
// })

// const relationCandidateChunks = computed(() => {
//   const keyword = relationSearchKeyword.value.trim().toLowerCase()
//   return relationSourceOptions.value.filter(item => {
//     if (item.id === relationSourceChunkId.value) {
//       return false
//     }

//     if (!keyword) {
//       return true
//     }

//     const content = ((item.procedure_name || item.text_content || '') as string).toLowerCase()
//     return content.includes(keyword)
//   })
// })

// const relationSourcePreview = computed(() => {
//   return relationSourceOptions.value.find(item => item.id === relationSourceChunkId.value) || null
// })

watch(selectedTenantCode, (tenantCode) => {
  if (tenantCode) {
    localStorage.setItem(TENANT_STORAGE_KEY, tenantCode)
  } else {
    localStorage.removeItem(TENANT_STORAGE_KEY)
  }

  newChunk.value.tenant_code = tenantCode
}, { immediate: true })

const chunkTenantOptions = computed(() => {
  const codeSet = new Set<string>()

  chunksData.value.forEach(item => {
    const code = normalizeTenantCode(item.tenant_code)
    if (code === 'temp') return
    codeSet.add(code)
  })

  return Array.from(codeSet).sort((a, b) => a.localeCompare(b, 'vi', { sensitivity: 'base' }))
})

const tenantChunkIds = computed(() => {
  if (!selectedTenantCode.value) {
    return new Set<string>()
  }

  return new Set(
    chunksData.value
      .filter(item => normalizeTenantCode(item.tenant_code) === selectedTenantCode.value)
      .map(item => item.id)
  )
})

const filteredChunks = computed(() => {
  const selectedChunkTenant = chunksTenantFilter.value

  return chunksData.value.filter(item => {
    const chunkIdMatch =
      !exactChunkIdFilter.value ||
      (item?.id ?? '').toString() === exactChunkIdFilter.value
    const tenantMatch =
      selectedChunkTenant === ALL_TENANTS_FILTER ||
      normalizeTenantCode(item.tenant_code) === selectedChunkTenant
    const categoryMatch = !categoryFilter.value || item.category === categoryFilter.value
    const subjectMatch = !subjectFilter.value || item.subject === subjectFilter.value
    
    const keywordMatch =
      !searchKeyword.value ||
      item.text_content
        ?.toLowerCase()
        .includes(searchKeyword.value.toLowerCase())

    return chunkIdMatch && tenantMatch && categoryMatch && subjectMatch && keywordMatch
  })
})

const filteredAlias = computed(() => {
  if (!selectedTenantCode.value) {
    return []
  }

  return aliasData.value.filter(item => {
    const tenantMatch =
      !selectedTenantCode.value ||
      tenantChunkIds.value.has(item.document_id)

    const keywordMatch =
      !searchKeyword.value ||
      item.alias_text
        ?.toLowerCase()
        .includes(searchKeyword.value.toLowerCase())

    return tenantMatch && keywordMatch
  })
})

const filteredTenants = computed(() => {
  const tenantMap = new Map<string, { tenant_code: string; chunk_count: number }>()

  chunksData.value.forEach(item => {
    const tenantCode = normalizeTenantCode(item.tenant_code)
    const current = tenantMap.get(tenantCode)

    if (tenantCode === 'temp') return

    if (current) {
      current.chunk_count += 1
    } else {
      tenantMap.set(tenantCode, {
        tenant_code: tenantCode,
        chunk_count: 1,
      })
    }
  })

  const keyword = searchKeyword.value.toLowerCase().trim()
  return Array.from(tenantMap.values())
    .filter(item => !keyword || item.tenant_code.toLowerCase().includes(keyword))
    .sort((a, b) => a.tenant_code.localeCompare(b.tenant_code, 'vi', { sensitivity: 'base' }))
})

const tenantScopeMap = computed(() => {
  const map = new Map<string, string>()

  tenantsData.value.forEach(item => {
    const tenantCode = normalizeTenantCode(item?.tenant_code)
    const scope = (item?.scope || '').toString().trim()
    if (tenantCode && scope) {
      map.set(tenantCode, scope)
    }
  })

  return map
})

function formatScopeLabel(scope: unknown) {
  const value = (scope ?? '').toString().trim()
  if (!value) return 'Quốc gia'
  if (value === 'xa_phuong') return 'Xã/Phường'
  if (value === 'tinh_thanh') return 'Tỉnh/Thành'
  if (value === 'quoc_gia') return 'Quốc gia'
  return value
}

function getChunkTenantScope(item: any) {
  const tenantCode = normalizeTenantCode(item?.tenant_code)
  const tenantScope = tenantScopeMap.value.get(tenantCode)
  if (tenantScope) return formatScopeLabel(tenantScope)

  const chunkScope = (item?.scope || '').toString().trim()
  return formatScopeLabel(chunkScope)
}

const filteredPrompts = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()

  return promptsData.value.filter(item => {
    if (!keyword) return true

    return (
      (item.prompt_name || '').toLowerCase().includes(keyword) ||
      (item.prompt_type || '').toLowerCase().includes(keyword) ||
      (item.content || '').toLowerCase().includes(keyword) ||
      (item.description || '').toLowerCase().includes(keyword)
    )
  })
})


const filteredLog = computed(() => {
  if (!selectedTenantCode.value) {
    return []
  }

  return logsData.value.filter(item => {
    const tenantMatch = !selectedTenantCode.value || normalizeTenantCode(item.tenant_code) === selectedTenantCode.value
    const typeLogMatch = !typeLogFilter.value || item.event_type === typeLogFilter.value

    const keywordMatch =
      !searchKeyword.value ||
      item.raw_query
        ?.toLowerCase()
        .includes(searchKeyword.value.toLowerCase())

    return tenantMatch && typeLogMatch && keywordMatch
  }).slice()
    .reverse()
})

function highlightText(text: string) {
  if (!searchKeyword.value) return text

  const keyword = searchKeyword.value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') // escape regex
  const regex = new RegExp(`(${keyword})`, 'gi')

  return text.replace(regex, '<mark class="highlight">$1</mark>')
}

async function loadChunks($load: boolean) {
  isLoading.value = true
  apiError.value = ''
  if ($load || chunksData.value.length === 0){
    try {
      const response = await fetch(`${API_BASE_URL}/get-chunks`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      })
      
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`)
      }
      
      const data = await response.json()
      console.log('Chunks data:', data)
      chunksData.value = data.chunks || []
    } catch (error: any) {
      apiError.value = `Connection error: ${error.message}`
    } finally {
      isLoading.value = false
    }
  }
}

async function loadLogs($load: boolean) {
  isLoading.value = true
  apiError.value = ''

  if (!selectedTenantCode.value) {
    logsData.value = []
    isLoading.value = false
    return
  }

  if ($load || logsData.value.length === 0){
    try {
      const params = new URLSearchParams()
      const tenantCode = toApiTenantCode(selectedTenantCode.value)
      if (tenantCode) {
        params.set('tenant_code', tenantCode)
      }

      const response = await fetch(`${API_BASE_URL}/get-logs${params.toString() ? `?${params.toString()}` : ''}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      })
      
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`)
      }
      
      const data = await response.json()
      console.log('Logs data:', data)
      logsData.value = data.logs || []
    } catch (error: any) {
      apiError.value = `Connection error: ${error.message}`
    } finally {
      isLoading.value = false
    }
  }
}

async function loadData() {
  loadChunks(false)
  loadAlias(false)
  loadPrompts(false)
  loadTenants(false)
}

async function loadAlias($load: boolean) {
  isLoading.value = true
  apiError.value = ''
  if ($load || aliasData.value.length === 0){
    try {
      const response = await fetch(`${API_BASE_URL}/get-alias`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      })
      
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`)
      }
      
      const data = await response.json()
      console.log('Alias data:', data)
      loadChunks(false);
      aliasData.value = data.alias || []
    } catch (error: any) {
      apiError.value = `Connection error: ${error.message}`
    } finally {
      isLoading.value = false
    }
  }
}

async function loadPrompts($load: boolean) {
  isLoading.value = true
  apiError.value = ''
  if ($load || promptsData.value.length === 0) {
    try {
      const response = await fetch(`${API_BASE_URL}/get-prompts`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      })

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`)
      }

      const data = await response.json()
      promptsData.value = data.prompts || []
    } catch (error: any) {
      apiError.value = `Connection error: ${error.message}`
    } finally {
      isLoading.value = false
    }
  }
}

async function loadTenants($load: boolean) {
  if ($load || tenantsData.value.length === 0){
    try {
      const response = await fetch(`${API_BASE_URL}/get-tenants`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      })
      
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`)
      }
      
      const data = await response.json()
      tenantsData.value = data.tenants || []
    } catch (error: any) {
      apiError.value = `Connection error: ${error.message}`
    }
  }
}


const viewChunks = () => {
  activeSection.value = 'chunks';
  loadChunks(false);
};

const viewAlias = () => {
  activeSection.value = 'alias';
  loadAlias(false);
};

const viewTenants = () => {
  activeSection.value = 'tenants';
  loadChunks(false);
};

const viewPrompts = () => {
  activeSection.value = 'prompts'
  loadPrompts(false)
}

const applyTenant = async (tenantCode: string) => {
  selectedTenantCode.value = tenantCode
  chunksTenantFilter.value = tenantCode
  responses.value = []
  searchKeyword.value = ''
  typeLogFilter.value = ''
  activeSection.value = 'chunks'

  await Promise.all([
    loadChunks(true),
    loadAlias(true),
    loadLogs(true),
    loadTenants(true),
    loadHistory(),
  ])
}

const clearTenantSelection = async () => {
  selectedTenantCode.value = null
  chunksTenantFilter.value = ALL_TENANTS_FILTER
  responses.value = []
  searchKeyword.value = ''
  typeLogFilter.value = ''

  await Promise.all([
    loadChunks(true),
    loadAlias(true),
    loadLogs(true),
    loadHistory(),
  ])
}

const viewLogs = () => {
  activeSection.value = 'log';
  loadLogs(false);
};

const viewAllTenantsChunks = () => {
  chunksTenantFilter.value = ALL_TENANTS_FILTER
  activeSection.value = 'chunks'
  loadChunks(false)
}

// const viewChunkRelations = () => {
//   activeSection.value = 'relations'
//   loadChunks(false)
// }

function startEditPrompt(item: any) {
  promptEditingId.value = item.id
  promptEditingData.value = {
    ...item,
    prompt_type: item.prompt_type ?? '',
    description: item.description ?? '',
  }
  isEditPromptModalOpen.value = true
}

function cancelEditPrompt() {
  isEditPromptModalOpen.value = false
  promptEditingId.value = null
  promptEditingData.value = null
}

async function saveEditPrompt() {
  if (!promptEditingId.value || !promptEditingData.value) return

  isSaving.value = true
  apiError.value = ''
  try {
    const payload = {
      prompt_name: (promptEditingData.value.prompt_name || '').trim(),
      prompt_type: (promptEditingData.value.prompt_type || '').trim(),
      content: (promptEditingData.value.content || '').trim(),
      description: (promptEditingData.value.description || '').trim() || null,
      version: Number(promptEditingData.value.version || 1),
      is_active: Boolean(promptEditingData.value.is_active),
    }

    if (!payload.prompt_type) {
      throw new Error('prompt_type không được để trống')
    }

    const response = await fetch(`${API_BASE_URL}/update-prompt/${promptEditingId.value}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}))
      throw new Error(errData.error || `API error: ${response.status}`)
    }

    await loadPrompts(true)
    cancelEditPrompt()
  } catch (error: any) {
    apiError.value = error.message
  } finally {
    isSaving.value = false
  }
}

async function submitCreatePrompt() {
  if (!newPrompt.value.prompt_name?.trim() || !newPrompt.value.prompt_type?.trim() || !newPrompt.value.content?.trim()) {
    alert('Vui lòng nhập tên prompt, prompt type và nội dung')
    return
  }

  isSaving.value = true
  apiError.value = ''
  try {
    const payload = {
      prompt_name: newPrompt.value.prompt_name.trim(),
      prompt_type: newPrompt.value.prompt_type.trim(),
      content: newPrompt.value.content.trim(),
      description: newPrompt.value.description?.trim() || null,
      version: Number(newPrompt.value.version || 1),
      is_active: Boolean(newPrompt.value.is_active),
    }

    const response = await fetch(`${API_BASE_URL}/create-prompt`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}))
      throw new Error(errData.error || `API error: ${response.status}`)
    }

    await loadPrompts(true)
    closeCreatePromptModal()
  } catch (error: any) {
    apiError.value = error.message
  } finally {
    isSaving.value = false
  }
}

function closeCreatePromptModal() {
  isCreatePromptModalOpen.value = false
  newPrompt.value = {
    prompt_name: '',
    prompt_type: '',
    content: '',
    description: '',
    version: 1,
    is_active: true,
  }
}

async function deletePrompt(promptId: string) {
  if (!confirm('Bạn có chắc chắn muốn xóa prompt này?')) {
    return
  }

  isSaving.value = true
  apiError.value = ''
  try {
    const response = await fetch(`${API_BASE_URL}/delete-prompt/${promptId}`, {
      method: 'DELETE'
    })

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}))
      throw new Error(errData.error || `API error: ${response.status}`)
    }

    await loadPrompts(true)
  } catch (error: any) {
    apiError.value = error.message
  } finally {
    isSaving.value = false
  }
}

async function togglePromptStatus(item: any) {
  isSaving.value = true
  apiError.value = ''
  try {
    const response = await fetch(`${API_BASE_URL}/toggle-prompt/${item.id}`, {
      method: 'POST'
    })

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}))
      throw new Error(errData.error || `API error: ${response.status}`)
    }

    await loadPrompts(true)
  } catch (error: any) {
    apiError.value = error.message
  } finally {
    isSaving.value = false
  }
}

async function clonePrompt(item: any) {
  isSaving.value = true
  apiError.value = ''
  try {
    const payload = {
      prompt_name: `${item.prompt_name} (Copy)`,
      prompt_type: item.prompt_type || '',
      content: item.content || '',
      description: item.description || null,
      version: Number(item.version || 1),
      is_active: false,
    }

    const response = await fetch(`${API_BASE_URL}/create-prompt`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}))
      throw new Error(errData.error || `API error: ${response.status}`)
    }

    await loadPrompts(true)
  } catch (error: any) {
    apiError.value = error.message
  } finally {
    isSaving.value = false
  }
}

function formatRelativePromptTime(value: string | null | undefined) {
  if (!value) return ''

  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return ''

  const diffMs = Date.now() - dt.getTime()
  const minuteMs = 60 * 1000
  const hourMs = 60 * minuteMs
  const dayMs = 24 * hourMs

  if (diffMs < hourMs) {
    const mins = Math.max(1, Math.floor(diffMs / minuteMs))
    return `Tạo ${mins} phút trước`
  }

  if (diffMs < dayMs) {
    const hours = Math.max(1, Math.floor(diffMs / hourMs))
    return `Tạo ${hours} giờ trước`
  }

  const days = Math.max(1, Math.floor(diffMs / dayMs))
  return `Tạo ${days} ngày trước`
}

// async function loadChunkRelations() {
//   if (!relationSourceChunkId.value) {
//     relationSelectedTargetIds.value = []
//     relationExistingTargetIds.value = new Set()
//     return
//   }

//   relationLoading.value = true
//   apiError.value = ''
//   try {
//     const params = new URLSearchParams({ source_chunk_id: relationSourceChunkId.value })
//     const tenantCode = toApiTenantCode(selectedTenantCode.value)
//     if (tenantCode) {
//       params.set('tenant_code', tenantCode)
//     }

//     const response = await fetch(`${API_BASE_URL}/chunk-relations?${params.toString()}`, {
//       method: 'GET',
//       headers: { 'Content-Type': 'application/json' }
//     })

//     if (!response.ok) {
//       throw new Error(`API error: ${response.status}`)
//     }

//     const data = await response.json()
//     const targetIds: string[] = (data.relations || [])
//       .map((item: any) => item.target_chunk_id)
//       .filter((id: unknown): id is string => typeof id === 'string' && id.length > 0)
//     relationExistingTargetIds.value = new Set(targetIds)
//     relationSelectedTargetIds.value = [...new Set(targetIds)]
//   } catch (error: any) {
//     apiError.value = `Connection error: ${error.message}`
//   } finally {
//     relationLoading.value = false
//   }
// }

// function toggleRelationTarget(targetId: string) {
//   const selected = relationSelectedTargetIds.value
//   if (selected.includes(targetId)) {
//     relationSelectedTargetIds.value = selected.filter(id => id !== targetId)
//     return
//   }
//   relationSelectedTargetIds.value = [...selected, targetId]
// }

// async function saveChunkRelations() {
//   if (!relationSourceChunkId.value) {
//     alert('Vui lòng chọn chunk nguồn')
//     return
//   }

//   const existing = relationExistingTargetIds.value
//   const selected = new Set(relationSelectedTargetIds.value)
//   const toCreate = [...selected].filter(id => !existing.has(id))
//   const toDelete = [...existing].filter(id => !selected.has(id))

//   if (toCreate.length === 0 && toDelete.length === 0) {
//     alert('Không có thay đổi để lưu')
//     return
//   }

//   relationLoading.value = true
//   apiError.value = ''
//   const tenantCode = toApiTenantCode(selectedTenantCode.value)

//   try {
//     if (toCreate.length > 0) {
//       const createRes = await fetch(`${API_BASE_URL}/chunk-relations/bulk-create`, {
//         method: 'POST',
//         headers: { 'Content-Type': 'application/json' },
//         body: JSON.stringify({
//           source_chunk_id: relationSourceChunkId.value,
//           tenant_code: tenantCode,
//           target_chunk_ids: toCreate,
//         })
//       })
//       if (!createRes.ok) {
//         throw new Error(`Create relations failed: ${createRes.status}`)
//       }
//     }

//     if (toDelete.length > 0) {
//       const deleteRes = await fetch(`${API_BASE_URL}/chunk-relations/bulk-delete`, {
//         method: 'POST',
//         headers: { 'Content-Type': 'application/json' },
//         body: JSON.stringify({
//           source_chunk_id: relationSourceChunkId.value,
//           tenant_code: tenantCode,
//           target_chunk_ids: toDelete,
//         })
//       })
//       if (!deleteRes.ok) {
//         throw new Error(`Delete relations failed: ${deleteRes.status}`)
//       }
//     }

//     await loadChunkRelations()
//     alert('Đã cập nhật liên kết chunk')
//   } catch (error: any) {
//     apiError.value = error.message
//   } finally {
//     relationLoading.value = false
//   }
// }

function startEdit(item: any) {
  originalData.value = { ...item }
  editingId.value = item.id
  editingData.value = { ...item,
    keywords: item.keywords ? [...item.keywords] : [],
    special_contexts: Array.isArray(item.special_contexts) ? [...item.special_contexts] : []
   }
  // Auto expand textarea on next tick
  setTimeout(() => {
    const textarea = document.querySelector('textarea.edit-input') as HTMLTextAreaElement
    if (textarea) {
      autoExpandTextarea(textarea)
    }
  }, 0)
}

function autoExpandTextarea(textarea: HTMLTextAreaElement) {
  textarea.style.height = 'auto'
  textarea.style.height = Math.min(textarea.scrollHeight, 300) + 'px'
}

function cancelEdit() {
  editingId.value = null
  editingData.value = null
}

async function confirmDeleteAlias() {
  if (!deleteTargetId.value) return

  isSaving.value = true

  try {
    const response = await fetch(
      `${API_BASE_URL}/delete-alias/${deleteTargetId.value}`,
      { method: 'DELETE' }
    )

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`)
    }

    aliasData.value = aliasData.value.filter(
      item => item.id !== deleteTargetId.value
    )

    closeDeleteModal()

  } catch (error: any) {
    apiError.value = error.message
  } finally {
    isSaving.value = false
  }
}


async function confirmDeleteChunk() {
  if (!deleteTargetId.value) return

  isSaving.value = true

  try {
    const response = await fetch(
      `${API_BASE_URL}/delete-chunk/${deleteTargetId.value}`,
      { method: 'DELETE' }
    )

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`)
    }

    chunksData.value = chunksData.value.filter(
      item => item.id !== deleteTargetId.value
    )

    closeDeleteModal()

  } catch (error: any) {
    apiError.value = error.message
  } finally {
    isSaving.value = false
  }
}


async function saveEditAlias() {
  if (!editingData.value) return
  isLoading.value = true
  isSaving.value = true

  try {
    const response = await fetch(`${API_BASE_URL}/update-alias/${editingId.value}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(editingData.value)
    })
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`)
    }
    
    // Update local data
    const idx = aliasData.value.findIndex(item => item.id === editingId.value)
    if (idx !== -1) {
      aliasData.value[idx] = editingData.value
    }
    
    editingId.value = null
    editingData.value = null
  } catch (error: any) {
    apiError.value = `Update error: ${error.message}`
  } finally {
    isLoading.value = false
    isSaving.value = false
  }
}

async function submitCreateChunk() {
  if (!newChunk.value.text_content) {
    alert('Vui lòng nhập đủ thông tin')
    return
  }

  const tenantCode = requireSelectedTenant('tạo chunk')
  if (!tenantCode) return

  isSaving.value = true

  try {
    let finalTenantCode = tenantCode

    // Nếu chọn scope tinh_thanh, check xem tenant hiện tại có parent_id không
    if (newChunk.value.scope === 'tinh_thanh') {
      const currentTenant = tenantsData.value.find(t => t.tenant_code === tenantCode)
      if (currentTenant && currentTenant.parent_id) {
        // Tìm parent tenant để lấy parent_tenant_code
        const parentTenant = tenantsData.value.find(t => t.id === currentTenant.parent_id)
        if (parentTenant && parentTenant.tenant_code) {
          finalTenantCode = parentTenant.tenant_code
        }
      }
    }

    const payload = {
      ...newChunk.value,
      tenant_code: newChunk.value.scope === 'quoc_gia' ? null : finalTenantCode,
      organization_unit: newChunk.value.organization_unit,
    }

    const response = await fetch(`${API_BASE_URL}/create-chunk`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}))
      throw new Error(errData.error || `API error: ${response.status}`)
    }

    await loadChunks(true)

    closeCreateModalChunk()

  } catch (error: any) {
    apiError.value = error.message
  } finally {
    isSaving.value = false
  }
}

function closeCreateModalChunk() {
  isCreateChunkModalOpen.value = false
  chunkSearch.value = ''
  newChunk.value = {
    tenant_code: localStorage.getItem(TENANT_STORAGE_KEY),
    scope: 'xa_phuong',
    text_content: '',
    procedure_name: null,
    category: null,
    subject: null,
    organization_unit: null
  }
}

const isChanged = computed(() => {
  if (!originalData.value) return false

  const scChanged = JSON.stringify(editingData.value.special_contexts ?? []) !==
    JSON.stringify(originalData.value.special_contexts ?? [])

  return (
    editingData.value.text_content !== originalData.value.text_content ||
    editingData.value.category !== originalData.value.category ||
    editingData.value.subject !== originalData.value.subject ||
    editingData.value.procedure_action !== originalData.value.procedure_action ||
    scChanged
  )
})

// const SC_OPTIONS = [
//   'yeu_to_nuoc_ngoai',
//   'khu_vuc_bien_gioi',
//   'da_co_ho_so_giay_to_ca_nhan',
//   'uy_quyen',
//   'chon_quoc_tich',
//   'qua_han_dang_ky',
//   'mat_so_ho_tich_va_ban_chinh',
// ]

// const PA_OPTIONS = [
//   'dang_ky_moi', 'dang_ky_lai', 'cap_lai', 'cap_ban_sao', 'cap_phep',
//   'thay_doi', 'cai_chinh', 'bo_sung', 'xac_nhan', 'ghi_vao_so',
//   'giai_quyet', 'thong_bao', 'ho_tro', 'tro_cap', 'cham_dut',
//   'tam_ngung', 'tiep_tuc', 'chap_thuan', 'cong_bo_lai', 'cong_bo',
//   'cong_nhan', 'chuyen_truong', 'tuyen_sinh', 'xet_tuyen', 'xet_cap',
//   'phe_duyet', 'can_thiep', 'thu_hoi', 'giao', 'huy_bo',
//   'cam_tiep_xuc', 'thanh_toan',
// ]

// function removeSpecialContext(ctx: string) {
//   if (!editingData.value) return
//   editingData.value.special_contexts = editingData.value.special_contexts.filter((c: string) => c !== ctx)
// }

// function addSpecialContext(event: Event) {
//   const select = event.target as HTMLSelectElement
//   const val = select.value
//   if (!val || !editingData.value) return
//   if (!editingData.value.special_contexts.includes(val)) {
//     editingData.value.special_contexts.push(val)
//   }
//   select.value = ''
// }

async function saveEditChunk() {
  if (!editingData.value) return

  if (!isChanged.value) {
    alert("Không có thay đổi")
    return
  }
  
  isSaving.value = true
  try {
    const response = await fetch(`${API_BASE_URL}/update-chunk/${editingId.value}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(editingData.value)
    })
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`)
    }
    
    // Update local data
    const idx = chunksData.value.findIndex(item => item.id === editingId.value)
    if (idx !== -1) {
      chunksData.value[idx] = editingData.value
    }
    
    editingId.value = null
    editingData.value = null
  } catch (error: any) {
    apiError.value = `Update error: ${error.message}`
  } finally {
    isSaving.value = false
  }
}

function selectChunk(chunk: any) {
  newAlias.value.document_id = chunk.id
  chunkSearch.value = chunk.text_content.slice(0, 80)
  showChunkDropdown.value = false
}

async function submitCreateAlias() {
  if (!newAlias.value.alias_text) {
    alert('Vui lòng nhập đủ thông tin')
    return
  }

  isSaving.value = true

  try {
    const response = await fetch(`${API_BASE_URL}/create-alias`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newAlias.value)
    })

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`)
    }

    await loadAlias(true)

    closeCreateModal()

  } catch (error: any) {
    apiError.value = error.message
  } finally {
    isSaving.value = false
  }
}

function closeCreateModal() {
  isCreateModalOpen.value = false
  chunkSearch.value = ''
  newAlias.value = {
    alias_text: '',
    normalized_alias: '',
    document_id: null
  }
}

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
})

async function loadHistory(){
  try {
    const tenantCode = requireSelectedTenant('tải lịch sử hội thoại', false)
    if (!tenantCode) {
      messages.value = [
        { text: 'Xin chào! Tôi là trợ lý AI của UBND Phường.', from: 'bot' }
      ]
      return
    }

    const sessionId = localStorage.getItem("chat_session_id")
    if (!sessionId) {
      messages.value = [
        { text: 'Xin chào! Tôi là trợ lý AI của UBND Phường.', from: 'bot' }
      ]
      return
    }
    const response = await fetch(`${API_BASE_URL}/load-history`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, tenant_code: tenantCode })
    })
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`)
    }

    const data = await response.json()
    console.log('Logs data:', data)

    const historyMessages = data.logs.flatMap((item:any) => [
      { text: item.raw_query, from: 'user' },
      { text: item.answer, from: 'bot', thoughts: [], showThoughts: false }
    ])

    messages.value = [
      { text: 'Xin chào! Tôi là trợ lý AI của UBND Phường.', from: 'bot' },
      ...historyMessages
    ]

    messages.value = [
      { text: 'Xin chào! Tôi là trợ lý AI của UBND Phường.', from: 'bot' },
      ...historyMessages
    ]

  } catch (error: any) {
    apiError.value = `Connection error: ${error.message}`
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  loadData()
  loadHistory()
  document.addEventListener('click', handleClickOutside)
});
</script>

<template>
  <div style="display: flex; width: 100%; min-height: 100vh;">
    <aside class="sidebar">
      <div class="logo">
        <div class="logo-icon">💬</div>
        <div>
          <div class="logo-title">AI Chatbot</div>
          <div class="logo-sub">UBND Phường</div>
        </div>
      </div>

      <div class="menu">
        <div class="menu-section">Kho tri thức</div>
        <div 
          class="menu-item" 
          :class="{ active: activeSection === 'chunks' }"
          @click="viewChunks()"
        >Chunks</div>
        <div 
          class="menu-item" 
          :class="{ active: activeSection === 'alias' }"
          @click="viewAlias()"
        >Dữ liệu alias</div>
        <div
          class="menu-item"
          :class="{ active: activeSection === 'tenants' }"
          @click="viewTenants()"
        >Danh sách tenants</div>
        <div
          class="menu-item"
          :class="{ active: activeSection === 'prompts' }"
          @click="viewPrompts()"
        >System Prompt</div>
        <!-- <div
          class="menu-item"
          :class="{ active: activeSection === 'relations' }"
          @click="viewChunkRelations()"
        >Liên kết chunk</div> -->
        <div class="menu-section">Kiểm thử</div>
        <div 
          class="menu-item" 
          :class="{ active: activeSection === 'test' }"
          @click="activeSection = 'test'"
        >Xử lý Chat</div>
        <div
          class="menu-item"
          :class="{ active: activeSection === 'log' }"
          @click="viewLogs()"
        >Logs</div>

        <div v-if="selectedTenantCode" class="tenant-active-box">
          <div class="tenant-active-label">Tenant đang chọn</div>
          <div class="tenant-active-code">{{ selectedTenantCode }}</div>
          <button class="tenant-clear-btn" @click="clearTenantSelection">Bỏ chọn tenant</button>
        </div>
      </div>
    </aside>
    <!-- :class="{ 'with-chat': isOpen = true } -->
    <div class="table-wrapper" v-if="activeSection === 'test'" :class="{ 'with-chat': isOpen }">
      <button class="btn-create" @click="loadData()" style="display: flex; margin-top: 18px; margin-left: 43px;">
        <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-refresh-cw w-4 h-4"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"></path><path d="M21 3v5h-5"></path><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"></path><path d="M8 16H3v5"></path></svg>
        <span style="font-size: 0.95em; margin-top: 2.3px; margin-left: 10px; ">Reload kho tri thức</span>
      </button>
      <section class="data-table">
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th class="col-index">ID</th>
                <th class="col-content">Content</th>
                <th class="col-scope">Score</th>
              </tr>
            </thead>

            <tbody>
              <tr v-for="(item, idx) in responses" :key="idx">
                <td class="col-index">{{ idx + 1 }}</td>
                <td class="col-content">
                  <div class="content-text">
                    {{ item.text_content }}
                  </div>
                </td>
                <td class="col-scope">
                  <span class="badge">{{ item.confidence_score }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
    <section class="data-chunks-table" v-if="activeSection === 'alias'" :class="{ 'with-chat': isOpen }">
      <!-- Search -->
      <div class="search-box">
        <input 
          v-model="searchKeyword"
          type="text" 
          placeholder="Tìm kiếm alias text..." 
        />
        <button class="btn-create" @click="isCreateModalOpen = true" style="display: flex;" :disabled="!selectedTenantCode">
          <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-plus w-4 h-4"><path d="M5 12h14"></path><path d="M12 5v14"></path></svg>
          <span style="font-size: 0.95em; margin-top: 2.2px; margin-left: 10px;">Tạo alias</span>
        </button>
      </div>
      <div class="filter-result">Tìm thấy {{ filteredAlias.length }} / {{ aliasData.length }} kết quả</div>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th class="col-index">ID</th>
              <th class="col-index">Document</th>
              <th class="col-index">Alias text</th>
              <th class="col-index">Normalized alias</th>
              <th class="col-index">Actions</th>
            </tr>
          </thead>

          <tbody>
            <tr v-if="filteredAlias.length === 0">
              <td colspan="5" style="text-align: center; padding: 20px; color: #999;">
                {{ isLoading ? 'Đang tải...' : 'Không có dữ liệu' }}
              </td>
            </tr>
            <tr v-for="(item, idx) in filteredAlias" :key="idx">
              <td class="col-index">{{ idx + 1 }}</td>
              <td class="col-content" style="width: 50%;">
                <!-- Khi edit -->
                  <option 
                  v-for="chunk in chunksData.filter(chunk => chunk.id === item.document_id)" 
                  :key="chunk.id" 
                  :value="chunk.id"
                >
                  {{ (chunk.procedure_name || chunk.text_content).slice(0, 70) }}
                </option>
              </td>
              <td class="col-content" style="width: 40%;">
                <div v-if="editingId === item.id" class="edit-input-wrapper">
                  <textarea v-model="editingData.alias_text" class="edit-input" rows="3" @input="autoExpandTextarea($event.target as HTMLTextAreaElement)" required></textarea>
                </div>
                <div 
                  v-else 
                  class="content-text"
                  v-html="highlightText(item.alias_text)"
                ></div>
              </td>
              <td class="col-content">
                <div v-if="editingId === item.id" class="edit-input-wrapper">
                  <textarea v-model="editingData.normalized_alias" class="edit-input" rows="3" @input="autoExpandTextarea($event.target as HTMLTextAreaElement)" required></textarea>
                </div>
                <div 
                  v-else 
                  class="content-text"
                  v-html="item.normalized_alias"
                ></div>
              </td>
              <td class="col-index action-cell">
                <div v-if="editingId === item.id" class="action-buttons">
                  <button class="btn-save" @click="saveEditAlias()" :disabled="isSaving">💾</button>
                  <button class="btn-cancel" @click="cancelEdit()">❌</button>
                </div>
                <div v-else class="action-buttons">
                  <button class="btn-edit" @click="startEdit(item)">✏️</button>
                  <button class="btn-edit" @click="openDeleteModal(item.id)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-trash2 lucide-trash-2 w-4 h-4"><path d="M3 6h18"></path><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path><line x1="10" x2="10" y1="11" y2="17"></line><line x1="14" x2="14" y1="11" y2="17"></line></svg>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="data-chunks-table" v-if="activeSection === 'tenants'" :class="{ 'with-chat': isOpen }">
      <div class="search-box">
        <input
          v-model="searchKeyword"
          type="text"
          placeholder="Tìm kiếm tenant code..."
        />
      </div>
      <div class="filter-result">Tìm thấy {{ filteredTenants.length }} / {{ filteredTenants.length }} kết quả</div>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th class="col-index">ID</th>
              <th class="col-content" style="width: 44%;">Tenant code</th>
              <th class="col-index">Số chunks</th>
              <th class="col-index">Thao tác</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="filteredTenants.length === 0">
              <td colspan="4" style="text-align: center; padding: 20px; color: #999;">
                {{ isLoading ? 'Đang tải...' : 'Không có dữ liệu' }}
              </td>
            </tr>
            <tr>
              <td class="col-index">0</td>
              <td class="col-content" style="width: 44%;">
                <div class="content-text">Tất cả tenant</div>
              </td>
              <td class="col-index">{{ chunksData.length }}</td>
              <td class="col-index action-cell">
                <button
                  class="btn-create"
                  style="margin-right: 0;"
                  @click="viewAllTenantsChunks"
                >
                  Xem tất cả
                </button>
              </td>
            </tr>
            <tr v-for="(item, idx) in filteredTenants" :key="item.tenant_code">
              <td class="col-index">{{ idx + 1 }}</td>
              <td class="col-content" style="width: 44%;">
                <div class="content-text">{{ item.tenant_code }}</div>
              </td>
              <td class="col-index">{{ item.chunk_count }}</td>
              <td class="col-index action-cell">
                <button
                  v-if="selectedTenantCode !== item.tenant_code"
                  class="btn-create"
                  style="margin-right: 0;"
                  @click="applyTenant(item.tenant_code)"
                >
                  Chọn
                </button>
                <span v-else>Đang dùng</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="data-chunks-table" v-if="activeSection === 'prompts'" :class="{ 'with-chat': isOpen }">
      <div class="search-box">
        <input
          v-model="searchKeyword"
          type="text" 
          placeholder="Tìm kiếm prompt..."
        />
        <button class="btn-create" @click="isCreatePromptModalOpen = true" style="display: flex;">
          <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-plus w-4 h-4"><path d="M5 12h14"></path><path d="M12 5v14"></path></svg>
          <span style="font-size: 0.95em; margin-top: 2.2px; margin-left: 10px;">Tạo prompt</span>
        </button>
      </div>
      <div class="filter-result">Tìm thấy {{ filteredPrompts.length }} / {{ promptsData.length }} kết quả</div>
      <div class="prompt-cards">
        <div v-if="filteredPrompts.length === 0" class="prompt-empty">
          {{ isLoading ? 'Đang tải...' : 'Không có dữ liệu' }}
        </div>

        <article v-for="item in filteredPrompts" :key="item.id" class="prompt-card">
          <div class="prompt-card-head">
            <div class="prompt-title-wrap">
              <h3 class="prompt-title">{{ item.prompt_name }}</h3>
              <span class="prompt-chip">v{{ item.version }}</span>
              <span class="prompt-chip prompt-chip-muted">{{ item.prompt_type || 'untyped' }}</span>
            </div>

            <button class="prompt-toggle" :class="{ active: item.is_active }" @click="togglePromptStatus(item)" :disabled="isSaving">
              <span class="prompt-toggle-knob"></span>
            </button>
          </div>

          <div class="prompt-card-body">
            <p class="prompt-content-text">{{ item.content }}</p>
          </div>

          <div class="prompt-card-foot">
            <div class="prompt-time">{{ formatRelativePromptTime(item.created_at) }}</div>
            <div class="prompt-actions">
              <button class="prompt-action-btn" @click="startEditPrompt(item)">Sửa</button>
              <button class="prompt-action-btn" @click="clonePrompt(item)">Nhân bản</button>
              <button class="prompt-action-btn prompt-action-btn-danger" @click="deletePrompt(item.id)">Xóa</button>
            </div>
          </div>
        </article>
      </div>
    </section>
<!-- 
    <section class="data-chunks-table" v-if="activeSection === 'relations'" :class="{ 'with-chat': isOpen }">
      <div class="search-box" style="display: flex; gap: 12px; align-items: center;">
        <select
          v-model="relationSourceChunkId"
          class="filter-select"
          style="max-width: 520px;"
          @change="loadChunkRelations"
        >
          <option value="">Chọn chunk nguồn...</option>
          <option
            v-for="chunk in relationSourceOptions"
            :key="chunk.id"
            :value="chunk.id"
          >
            {{ (chunk.procedure_name || chunk.text_content || '').slice(0, 120) }}
          </option>
        </select>

        <input
          v-model="relationSearchKeyword"
          type="text"
          placeholder="Lọc chunk đích theo nội dung..."
          style="max-width: 420px;"
        />

        <button
          class="btn-create"
          @click="saveChunkRelations"
          :disabled="relationLoading || !relationSourceChunkId"
        >
          {{ relationLoading ? 'Đang lưu...' : 'Lưu liên kết' }}
        </button>
      </div>

      <div class="filter-result">
        Nguồn: {{ relationSourcePreview ? (relationSourcePreview.procedure_name || relationSourcePreview.text_content || '').slice(0, 100) : 'Chưa chọn' }}
      </div>

      <div class="filter-result" style="background: #f8fafc; color: #334155;">
        Đã chọn {{ relationSelectedTargetIds.length }} chunk đích.
      </div>

      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th class="col-index">Chọn</th>
              <th class="col-index">STT</th>
              <th class="col-content">Chunk đích</th>
              <th class="col-index">Đang liên kết</th>
            </tr>
          </thead>

          <tbody>
            <tr v-if="!relationSourceChunkId">
              <td colspan="4" style="text-align: center; padding: 20px; color: #999;">
                Vui lòng chọn chunk nguồn để quản lý liên kết.
              </td>
            </tr>
            <tr v-else-if="relationCandidateChunks.length === 0">
              <td colspan="4" style="text-align: center; padding: 20px; color: #999;">
                Không có chunk đích phù hợp.
              </td>
            </tr>
            <tr v-for="(item, idx) in relationCandidateChunks" :key="item.id">
              <td class="col-index">
                <input
                  type="checkbox"
                  :checked="relationSelectedTargetIds.includes(item.id)"
                  @change="toggleRelationTarget(item.id)"
                />
              </td>
              <td class="col-index">{{ idx + 1 }}</td>
              <td class="col-content">
                <div class="content-text">{{ item.procedure_name || item.text_content }}</div>
              </td>
              <td class="col-index">
                <span v-if="relationExistingTargetIds.has(item.id)">Yes</span>
                <span v-else>-</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section> -->

    <section class="data-chunks-table" v-if="activeSection === 'log'" :class="{ 'with-chat': isOpen }">
      <!-- Search -->
      <div class="search-box">
        <input 
          v-model="searchKeyword"
          type="text" 
          placeholder="Tìm kiếm nội dung..." 
        />
      </div>
      <div class="filter-group" style="margin: 18px;">
          <label>Loại log:</label>
          <select v-model="typeLogFilter" class="filter-select">
            <option value="">Tất cả</option>
            <option value="complaint">Phàn nàn/ý kiến</option>
            <option value="out_of_scope">Ngoài phạm vi</option>
            <option value="normal">Lịch sử hội thoại</option>
            <option value="low_confidence">Các câu hỏi điểm thấp</option>
            
          </select>
        <button class="btn-reset-filter" @click="typeLogFilter = '';">Xóa bộ lọc</button>
      </div>
      <div class="filter-result">Tìm thấy {{ filteredLog.length }} / {{ filteredLog.length }} kết quả</div>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th class="col-index">Note</th>
              <th class="col-index">ID</th>
              <th class="col-question">Câu hỏi</th>
              <th class="col-question">Câu hỏi đã chuẩn hóa</th>
              <th class="col-index">Category</th>
              <th class="col-index">Subject</th>
              <th class="col-question">Câu trả lời</th>
              <th class="col-index">Loại phản hồi</th>
              <th class="col-reason">Lý do</th>
              <th class="col-index">Điểm so Alias</th>
              <th class="col-index">Điểm so tài liệu</th>
              <th class="col-index">Điểm tổng</th>
              <th class="col-index">Thời gian (s)</th>
            </tr>
          </thead>

          <tbody>
            <tr v-if="filteredLog.length === 0">
              <td colspan="5" style="text-align: center; padding: 20px; color: #999;">
                {{ isLoading ? 'Đang tải...' : 'Không có dữ liệu' }}
              </td>
            </tr>
            <tr v-for="(item, idx) in filteredLog" :key="idx" :class="{ noted: item.is_noted }">
              <td class="col-index">
                <button class="btn-note" @click="toggleNote(item)">
                  ⭐
                </button>
              </td>
              <td class="col-index">{{ idx + 1 }}</td>
              <td class="col-content" style="width: 40%;">
                <div 
                  class="content-text"
                  v-html="highlightText(item.raw_query)"
                ></div>
              </td>
              <td class="col-content" style="width: 40%;">
                <div 
                  class="content-text"
                  v-html="highlightText(item.expanded_query)"
                ></div>
              </td>
              <td class="col-index">
                <span>{{ item.detected_category || '-' }}</span>
              </td>
              <td class="col-index">
                <span>{{ item.detected_subject || '-' }}</span>
              </td>
              <td class="col-content" style="width: 40%;">
                <div 
                  class="content-text"
                  v-html="highlightText(item.answer)"
                ></div>
              </td>
              <td class="col-index">
                <span>{{ item.event_type || '-' }}</span>
              </td>
              <td class="col-content">
                <span>{{ item.reason || '-' }}</span>
              </td>
              <td class="col-index">
                <span>{{ item.alias_score || '-' }}</span>
              </td>
              <td class="col-index">
                <span>{{ item.document_score || '-' }}</span>
              </td>
              <td class="col-index">
                <span>{{ item.confidence_score || '-' }}</span>
              </td>
              <td class="col-index">
                <span>{{ item.response_time_ms || '-' }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="data-chunks-table" v-if="activeSection === 'chunks'" :class="{ 'with-chat': isOpen }">
      <!-- Search -->
      <div class="search-box">
        <input 
          v-model="searchKeyword"
          type="text" 
          placeholder="Tìm kiếm nội dung..." 
        />
        <button class="btn-create" @click="isCreateChunkModalOpen = true" style="display: flex;" :disabled="!selectedTenantCode">
          <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-plus w-4 h-4"><path d="M5 12h14"></path><path d="M12 5v14"></path></svg>
          <span style="font-size: 0.95em; margin-top: 2.2px; margin-left: 10px;">Tạo chunk</span>
        </button>
      </div>
      <!-- Filter Section -->
      <div class="filter-section">
        <div class="filter-group">
          <label>Tenant:</label>
          <select v-model="chunksTenantFilter" class="filter-select">
            <option :value="ALL_TENANTS_FILTER">Tất cả tenant</option>
            <option v-for="tenantCode in chunkTenantOptions" :key="tenantCode" :value="tenantCode">
              {{ tenantCode }}
            </option>
          </select>
        </div>
        <div class="filter-group">
          <label>Category:</label>
          <select v-model="categoryFilter" class="filter-select">
            <option value="">Tất cả</option>
            <option value="thong_tin_tong_quan">Thông tin tổng quan</option>
            <option value="to_chuc_bo_may">Tổ chức bộ máy</option>
            <option value="thu_tuc_hanh_chinh">Thủ tục hành chính</option>
            <option value="phan_anh_kien_nghi">Phản ánh kiến nghị</option>
          </select>
        </div>
        <div class="filter-group">
          <label>Subject:</label>
          <select v-if="categoryFilter == 'thu_tuc_hanh_chinh'" v-model="subjectFilter" class="filter-select">
            <option value="">Tất cả</option>
            <option value="tu_phap_ho_tich">Tư pháp hộ tịch</option>
            <option value="doanh_nghiep">Doanh nghiệp</option>
            <option value="giao_thong_van_tai">Giao thông vận tải</option>
            <option value="dat_dai">Đất đai</option>
            <option value="xay_dung_nha_o">Xây dựng nhà ở</option>
            <option value="dau_tu">Đầu tư</option>
            
            <option value="lao_dong_viec_lam">Lao động việc làm</option>
            <option value="bao_hiem_an_sinh">Bảo hiểm an sinh</option>
            <option value="giao_duc_dao_tao">Giáo dục đào tạo</option>
            <option value="y_te">Y tế</option>
            <option value="tai_nguyen_moi_truong">Tài nguyên môi trường</option>
            <option value="van_hoa_the_thao_du_lich">Văn hóa thể thao du lịch</option>
            
            <option value="khoa_hoc_cong_nghe">Khoa học công nghệ</option>
            <option value="thong_tin_truyen_thong">Thông tin truyền thông</option>
            <option value="nong_nghiep">Nông nghiệp</option>
            <option value="cong_thuong">Công thương</option>
            <option value="tai_chinh_thue_phi">Tài chính thuế phí</option>
          </select>
          <select v-if="categoryFilter == 'thong_tin_tong_quan'" v-model="subjectFilter" class="filter-select">
            <option value="">Tất cả</option>
            <option value="gioi_thieu_dia_phuong">Giới thiệu địa phương</option>
            <option value="lich_su_hanh_chinh">Lịch sử hành chính</option>
            <option value="dia_ly">Địa lý</option>
            <option value="thong_ke">Thống kê</option>
            <option value="co_cau_to_chuc">Cơ cấu tổ chức</option>
            <option value="giao_thong">Giao thông</option>
            <option value="lich_lam_viec">Lịch làm việc</option>
            <option value="thong_tin_lien_he">Thông tin liên hệ</option> 

            <option value="gioi_thieu_chung">Giới thiệu chung</option>
            <option value="chuc_nang_nhiem_vu">Chức năng nhiệm vụ</option>
            <option value="hoi_vien_doi_tuong_phuc_vu">Hội viên đối tượng phục vụ</option>
            <option value="hoat_dong_phong_trao">Hoạt động phong trào</option>
            <option value="chuong_trinh_ho_tro">Chương trình hỗ trợ</option>
            <option value="thu_tuc_quy_trinh">Thủ tục quy trình</option>
            <option value="quy_dinh_huong_dan">Quy định hướng dẫn</option>
          </select>
          <select v-if="categoryFilter == 'to_chuc_bo_may'" v-model="subjectFilter" class="filter-select">
            <option value="">Tất cả</option>
            <option value="nhan_su">Nhân sự</option>
            <option value="chuc_vu">Chức vụ</option>
          </select>
          <select v-if="categoryFilter == 'phan_anh_kien_nghi'" v-model="subjectFilter" class="filter-select">
            <option value="">Tất cả</option>
            <option value="ha_tang">Hạ tầng</option>
            <option value="moi_truong">Môi trường</option>
            <option value="an_ninh_trat_tu">An ninh trật tự</option>
            <option value="do_thi">Đô thị</option>
            <option value="giao_thong">Giao thông</option>
            <option value="khieu_nai_to_cao">Khiếu nại tố cáo</option>
          </select>
        </div>
        <button class="btn-reset-filter" @click="categoryFilter = ''; subjectFilter = ''; exactChunkIdFilter = ''">Xóa bộ lọc</button>
      </div>
      <div v-if="exactChunkIdFilter" class="filter-result" style="background: #eef6ff; color: #1d4ed8;">
        Đang lọc theo chunk ID: {{ exactChunkIdFilter }}
      </div>
      <div class="filter-result">Tìm thấy {{ filteredChunks.length }} / {{ chunksData.length }} kết quả</div>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th class="col-index">ID</th>
              <th class="col-content sortable" @click="toggleSortText">
                Text Content
                <span v-if="sortBy === 'text_content'">
                  {{ sortDir === 'asc' ? '▲' : '▼' }}
                </span>
              </th>
              <th class="col-index">Category</th>
              <th class="col-index">Subject</th>
              <th class="col-index">Scope</th>
              <th class="col-index">metadata</th>
              <!-- <th class="col-index">procedure_action</th>
              <th class="col-index">special_contexts</th> -->
              <!-- <th class="col-index">Keywords</th> -->
              <th class="col-index">Actions</th>
            </tr>
          </thead>

          <tbody>
            <tr v-if="chunksData.length === 0">
              <td colspan="8" style="text-align: center; padding: 20px; color: #999;">
                {{ isLoading ? 'Đang tải...' : 'Không có dữ liệu' }}
              </td>
            </tr>
            <tr
              v-for="(item, idx) in sortedFilteredChunks"
              :id="`chunk-row-${item.id}`"
              :key="item.id || idx"
              :class="{ 'chunk-row-focused': exactChunkIdFilter && String(item.id) === exactChunkIdFilter }"
            >
              <td class="col-index">{{ idx + 1 }}</td>
              <td class="col-content">
                <div v-if="editingId === item.id" class="edit-input-wrapper">
                  <textarea v-model="editingData.text_content" class="edit-input" rows="3" @input="autoExpandTextarea($event.target as HTMLTextAreaElement)"></textarea>
                </div>
                <div 
                  v-else 
                  class="content-text"
                  v-html="highlightText(item.text_content)"
                ></div>
              </td>
              <td class="col-index">
                <div v-if="editingId === item.id" class="edit-input-wrapper">
                  <select v-model="editingData.category" class="edit-input edit-select">
                    <option value="">-- Chọn --</option>
                    <option value="thong_tin_tong_quan">Thông tin tổng quan</option>
                    <option value="to_chuc_bo_may">Tổ chức bộ máy</option>
                    <option value="thu_tuc_hanh_chinh">Thủ tục hành chính</option>
                    <option value="phan_anh_kien_nghi">Phản ánh kiến nghị</option>
                  </select>
                </div>
                <span v-else>{{ item.category || '-' }}</span>
              </td>
              <td class="col-index">
                <div v-if="editingId === item.id">
                    <div v-if="editingData.category === 'thu_tuc_hanh_chinh'" class="edit-input-wrapper">
                      <select v-model="editingData.subject" class="edit-input edit-select">
                        <option value="">-- Chọn --</option>
                        <option value="tu_phap_ho_tich">Tư pháp hộ tịch</option>
                        <option value="doanh_nghiep">Doanh nghiệp</option>
                        <option value="giao_thong_van_tai">Giao thông vận tải</option>
                        <option value="dat_dai">Đất đai</option>
                        <option value="xay_dung_nha_o">Xây dựng nhà ở</option>
                        <option value="dau_tu">Đầu tư</option>
                        
                        <option value="lao_dong_viec_lam">Lao động việc làm</option>
                        <option value="bao_hiem_an_sinh">Bảo hiểm an sinh</option>
                        <option value="giao_duc_dao_tao">Giáo dục đào tạo</option>
                        <option value="y_te">Y tế</option>
                        <option value="tai_nguyen_moi_truong">Tài nguyên môi trường</option>
                        <option value="van_hoa_the_thao_du_lich">Văn hóa thể thao du lịch</option>
                        
                        <option value="khoa_hoc_cong_nghe">Khoa học công nghệ</option>
                        <option value="thong_tin_truyen_thong">Thông tin truyền thông</option>
                        <option value="nong_nghiep">Nông nghiệp</option>
                        <option value="cong_thuong">Công thương</option>
                        <option value="tai_chinh_thue_phi">Tài chính thuế phí</option>
                      </select>
                    </div>
                    <div v-if="editingData.category === 'thong_tin_tong_quan'" class="edit-input-wrapper">
                      <select v-model="editingData.subject" class="edit-input edit-select">
                        <option value="">-- Chọn --</option>
                        <option value="gioi_thieu_dia_phuong">Giới thiệu địa phương</option>
                        <option value="lich_su_hanh_chinh">Lịch sử hành chính</option>
                        <option value="dia_ly">Địa lý</option>
                        <option value="thong_ke">Thống kê</option>
                        <option value="co_cau_to_chuc">Cơ cấu tổ chức</option>
                        <option value="giao_thong">Giao thông</option>
                        <option value="lich_lam_viec">Lịch làm việc</option>
                        <option value="thong_tin_lien_he">Thông tin liên hệ</option>

                        <option value="gioi_thieu_chung">Giới thiệu chung</option>
                        <option value="chuc_nang_nhiem_vu">Chức năng nhiệm vụ</option>
                        <option value="hoi_vien_doi_tuong_phuc_vu">Hội viên đối tượng phục vụ</option>
                        <option value="hoat_dong_phong_trao">Hoạt động phong trào</option>
                        <option value="chuong_trinh_ho_tro">Chương trình hỗ trợ</option>
                        <option value="thu_tuc_quy_trinh">Thủ tục quy trình</option>
                        <option value="quy_dinh_huong_dan">Quy định hướng dẫn</option>
                      </select>
                    </div>
                    <div v-if="editingData.category === 'to_chuc_bo_may'" class="edit-input-wrapper">
                      <select v-model="editingData.subject" class="edit-input edit-select">
                        <option value="">-- Chọn --</option>
                        <option value="nhan_su">Nhân sự</option>
                        <option value="chuc_vu">Chức vụ</option>
                      </select>
                    </div>
                    <div v-if="editingData.category === 'phan_anh_kien_nghi'" class="edit-input-wrapper">
                      <select v-model="editingData.subject" class="edit-input edit-select">
                        <option value="">-- Chọn --</option>
                        <option value="ha_tang">Hạ tầng</option>
                        <option value="moi_truong">Môi trường</option>
                        <option value="an_ninh_trat_tu">An ninh trật tự</option>
                        <option value="do_thi">Đô thị</option>
                        <option value="giao_thong">Giao thông</option>
                        <option value="khieu_nai_to_cao">Khiếu nại tố cáo</option>
                      </select>
                    </div>
                </div>
                <span v-else>{{ item.subject || '-' }}</span>
              </td>
              <td class="col-index">
                <span>{{ getChunkTenantScope(item) }}</span>
              </td>
              <!-- <td class="col-index">
                <div v-if="editingId === item.id" class="edit-input-wrapper sc-editor">
                  <div v-if="editingData.procedure_action" class="sc-badge-group sc-edit-tags">
                    <span class="sc-badge pa-badge">
                      {{ editingData.procedure_action }}
                      <button class="sc-remove-btn" @click="editingData.procedure_action = null" title="Xóa">×</button>
                    </span>
                  </div>
                  <select
                    v-if="!editingData.procedure_action"
                    class="edit-input edit-select sc-add-select"
                    @change="editingData.procedure_action = ($event.target as HTMLSelectElement).value || null"
                  >
                    <option value="">-- Chọn --</option>
                    <option v-for="opt in PA_OPTIONS" :key="opt" :value="opt">{{ opt }}</option>
                  </select>
                </div>
                <div v-else class="sc-badge-group">
                  <span v-if="item.procedure_action" class="sc-badge pa-badge">{{ item.procedure_action }}</span>
                  <span v-else>-</span>
                </div>
              </td>
              <td class="col-index">
                <div v-if="editingId === item.id" class="edit-input-wrapper sc-editor">
                  <div class="sc-badge-group sc-edit-tags">
                    <span
                      v-for="ctx in editingData.special_contexts"
                      :key="ctx"
                      :class="['sc-badge', 'sc-' + ctx]"
                    >
                      {{ ctx }}
                      <button class="sc-remove-btn" @click="removeSpecialContext(ctx)" title="Xóa">×</button>
                    </span>
                  </div>
                  <select class="edit-input edit-select sc-add-select" @change="addSpecialContext($event)">
                    <option value="">+ Thêm...</option>
                    <option
                      v-for="opt in SC_OPTIONS.filter(o => !editingData.special_contexts.includes(o))"
                      :key="opt"
                      :value="opt"
                    >{{ opt }}</option>
                  </select>
                </div>
                <div v-else class="sc-badge-group">
                  <template v-if="Array.isArray(item.special_contexts) && item.special_contexts.length">
                    <span
                      v-for="ctx in item.special_contexts"
                      :key="ctx"
                      :class="['sc-badge', 'sc-' + ctx]"
                    >{{ ctx }}</span>
                  </template>
                  <span v-else>-</span>
                </div>
              </td> -->
              <td class="col-index">
                <div v-if="editingId === item.id" class="edit-input-wrapper">
                  <select v-model="editingData.procedure_action" class="edit-input edit-select">
                    <option value="">Uỷ ban nhân dân</option>
                    <option value="doan_thanh_nien">Đoàn thanh niên</option>
                    <option value="hoi_phu_nu">Hội phụ nữ</option>
                    <option value="mttq">Mặt trận Tổ quốc</option>
                    <option value="cong_doan">Công đoàn</option>
                  </select>
                </div>
                <span v-else>{{ item.procedure_action || 'UBND' }}</span>
              </td>
              <td class="col-index action-cell">
                <div v-if="editingId === item.id" class="action-buttons">
                  <button class="btn-save" @click="saveEditChunk()" :disabled="isSaving">💾</button>
                  <button class="btn-cancel" @click="cancelEdit()">❌</button>
                </div>
                <div v-else class="action-buttons">
                  <button class="btn-edit" @click="startEdit(item)">✏️</button>
                  <button class="btn-edit" @click="openDeleteModalChunk(item.id)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-trash2 lucide-trash-2 w-4 h-4"><path d="M3 6h18"></path><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path><line x1="10" x2="10" y1="11" y2="17"></line><line x1="14" x2="14" y1="11" y2="17"></line></svg>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
    <!-- Chat Section -->
    <section v-if="activeSection === 'test'" class="chat-section">
      <!-- Header -->
      <div class="chat-header">
        <div class="chat-title">
          <span class="dot"></span>
          Chatbot 1.0
        </div>
        <!-- ⚙ Setting button -->
    <!-- Dropdown -->
    <div v-if="showSettings" class="settings-dropdown">
      
      <!-- Toggle LLM -->
      <div class="setting-item">
        <label>
          <input type="checkbox" v-model="isLLMEnabled" />
          Sử dụng LLM trả lời
        </label>
      </div>

        <!-- Chunk limit -->
        <div class="setting-item">
          <label>Số chunks trả lời: </label>
          <input 
            type="number" 
            v-model.number="chunkLimit"
            min="1"
            max="6"
          />
        </div>

      </div>
        <button class="close-btn" @click="clearChat()" title="Xóa lịch sử hội thoại">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-refresh-cw w-4 h-4"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"></path><path d="M21 3v5h-5"></path><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"></path><path d="M8 16H3v5"></path></svg>
        </button>
      </div>

      <!-- Messages -->
      <div 
        class="chat-body"
        ref="chatBody"
        @scroll="handleChatBodyScroll"
      >
        <div 
          v-for="(msg, idx) in messages" 
          :key="idx" 
          :class="msg.from + '-message'"
        >
          <div class="message-bubble">
          <div
            v-if="msg.from === 'bot' && msg.isThinking && !msg.text"
            class="thinking-state"
          >
            <div class="thinking-bubble" aria-label="Đang suy nghĩ">
              <span></span>
              <span></span>
              <span></span>
            </div>
            <div
              v-if="getThinkingThought(msg)"
              class="thinking-thought-line"
            >
              {{ getThinkingThought(msg) }}
            </div>
          </div>
          <!-- <button
            v-if="msg.from === 'bot' && msg.thoughts && msg.thoughts.length && !(msg.isThinking && !msg.text)"
            class="thought-toggle"
            @click="toggleThoughts(msg)"
          >
            {{ msg.showThoughts ? 'Ẩn suy nghĩ' : (msg.isThinking ? `Đang suy nghĩ (${msg.thoughts.length})` : `Xem suy nghĩ (${msg.thoughts.length})`) }}
          </button> -->
          <!-- <div
            v-if="msg.from === 'bot' && msg.showThoughts && msg.thoughts && msg.thoughts.length"
            class="thought-box"
          >
            <div
              v-for="(thought, tIdx) in msg.thoughts"
              :key="tIdx"
              class="thought-item"
            >
              {{ thought }}
            </div>
          </div> -->
          <div
            v-if="msg.text"
            class="message-markdown"
            v-html="renderMarkdown(msg.text)"
          ></div>
          <button
            v-if="msg.from === 'bot' && msg.chunks && msg.chunks.length > 0"
            class="btn-view-chunks"
            @click="viewChunksFromMessage(msg.chunks)"
          >
            📄 Xem {{ msg.chunks.length }} tài liệu tham khảo
          </button>
          </div>
          <div v-if="msg.text && formatMessageTime(msg.createdAt)" class="message-time">
            {{ formatMessageTime(msg.createdAt) }}
          </div>
        </div>
      </div>

      <!-- Input -->
      <div class="chat-footer">
        <input
          v-model="userInput"
          :disabled="!selectedTenantCode"
          :placeholder="selectedTenantCode ? 'Nhập câu hỏi của bạn...' : 'Chọn tenant để bắt đầu thao tác'"
          @keyup.enter="sendMessage"
        />
        <button @click="sendMessage" :disabled="loadingChat || !selectedTenantCode">{{ loadingChat ? '⏳' : '➤' }}</button>
      </div>
      <!-- Debug Log Panel -->
        <div class="log-panel" ref="logPanel">
          <div class="log-header" @mousedown="startDrag">
            <span>Debug Log</span>
            <button @click="clearLogs">Clear</button>
          </div>

          <div class="log-body" ref="logBody">
            <div 
              v-for="(log, index) in logs" 
              :key="index"
              :class="['log-item', log.type]"
            >
              {{ log.message }}
            </div>
          </div>
        </div>
    </section>
    <!-- Create Alias Modal -->
    <div v-if="isCreateModalOpen" class="modal-overlay">
      <div class="modal-box">

        <h3>Tạo Alias Mới</h3>

        <label>Alias text</label>
        <textarea 
          v-model="newAlias.alias_text" 
          class="edit-input"
        ></textarea>

        <label>Chọn Chunk</label>

        <div class="autocomplete-wrapper">

          <input
            v-model="chunkSearch"
            class="edit-input"
            placeholder="Tìm nội dung chunk..."
            @focus="showChunkDropdown = true"
          />

          <div 
            v-if="showChunkDropdown && filteredChunksForSelect.length"
            class="autocomplete-dropdown"
          >
            <div
              v-for="chunk in filteredChunksForSelect"
              :key="chunk.id"
              class="autocomplete-item"
              @click="selectChunk(chunk)"
              v-html="highlightChunk(chunk.text_content.slice(0, 120))"
            ></div>
          </div>

        </div>

        <div class="modal-actions">
          <button class="btn-save" @click="submitCreateAlias" :disabled="isSaving">💾 Lưu</button>
          <button class="btn-cancel" @click="closeCreateModal">Hủy</button>
        </div>

      </div>
    </div>

    <div v-if="isCreateChunkModalOpen" class="modal-overlay">
      <div class="modal-box">

        <h2>Tạo Chunk Mới</h2>
        <!-- <div v-if="newChunk.category == 'thu_tuc_hanh_chinh'" style="display: flex; flex-direction: column;">
          <label style="font-size: 1.2em; margin-bottom: 16px;">Tên thủ tục (Nếu có)</label>
          <textarea 
            v-model="newChunk.procedure_name" 
            class="edit-input" style="font-size: 1.2em;"
          ></textarea>
        </div> -->
        <label style="font-size: 1.2em;">Nội dung chunk</label>
        <textarea 
          v-model="newChunk.text_content" 
          class="edit-input" style="min-height: 218px; font-size: 1.2em;"
        ></textarea>
        <div class="filter-section">
          <div class="filter-group">
            <label>Tổ chức:</label>
            <select v-model="newChunk.organization_unit" class="filter-select">
              <option value="ubnd">UBND</option>
              <option value="doan_thanh_nien">Đoàn thanh niên</option>
              <option value="hoi_phu_nu">Hội phụ nữ</option>
              <option value="cong_doan">Công đoàn</option>
              <option value="mttq">Mặt trận tổ quốc</option>
            </select>
          </div>
          <div class="filter-group">
            <label>Category:</label>
            <select v-if="newChunk.organization_unit == 'ubnd'" v-model="newChunk.category" class="filter-select">
              <option value="thong_tin_tong_quan">Thông tin tổng quan</option>
              <option value="to_chuc_bo_may">Tổ chức bộ máy</option>
              <option value="thu_tuc_hanh_chinh">Thủ tục hành chính</option>
              <option value="phan_anh_kien_nghi">Phản ánh kiện nghị</option>
            </select>
            <select v-else v-model="newChunk.category" class="filter-select">
              <option value="thong_tin_tong_quan">Thông tin tổng quan</option>
              <option value="to_chuc_bo_may">Tổ chức bộ máy</option>
            </select>
          </div>
          <div v-if="newChunk.organization_unit == 'ubnd'" class="filter-group">
            <label>Subject:</label>
            <select v-if="newChunk.category == 'thu_tuc_hanh_chinh'" v-model="newChunk.subject" class="filter-select">
              <option value="">-</option>
              <option value="tu_phap_ho_tich">Tư pháp hộ tịch</option>
              <option value="doanh_nghiep">Doanh nghiệp</option>
              <option value="giao_thong_van_tai">Giao thông vận tải</option>
              <option value="dat_dai">Đất đai</option>
              <option value="xay_dung_nha_o">Xây dựng nhà ở</option>
              <option value="dau_tu">Đầu tư</option>
              
              <option value="lao_dong_viec_lam">Lao động việc làm</option>
              <option value="bao_hiem_an_sinh">Bảo hiểm an sinh</option>
              <option value="giao_duc_dao_tao">Giáo dục đào tạo</option>
              <option value="y_te">Y tế</option>
              <option value="tai_nguyen_moi_truong">Tài nguyên môi trường</option>
              <option value="van_hoa_the_thao_du_lich">Văn hóa thể thao du lịch</option>
              
              <option value="khoa_hoc_cong_nghe">Khoa học công nghệ</option>
              <option value="thong_tin_truyen_thong">Thông tin truyền thông</option>
              <option value="nong_nghiep">Nông nghiệp</option>
              <option value="cong_thuong">Công thương</option>
              <option value="tai_chinh_thue_phi">Tài chính thuế phí</option>
            </select>
            <select v-if="newChunk.category == 'thong_tin_tong_quan'" v-model="newChunk.subject" class="filter-select">
              <option value="gioi_thieu_dia_phuong">Giới thiệu địa phương</option>
              <option value="lich_su_hanh_chinh">Lịch sử hành chính</option>
              <option value="dia_ly">Địa lý</option>
              <option value="thong_ke">Thống kê</option>
              <option value="co_cau_to_chuc">Cơ cấu tổ chức</option>
              <option value="giao_thong">Giao thông</option>
              <option value="lich_lam_viec">Lịch làm việc</option>
              <option value="thong_tin_lien_he">Thông tin liên hệ</option>
            </select>
            <select v-if="newChunk.category == 'to_chuc_bo_may'" v-model="newChunk.subject" class="filter-select">
              <option value="nhan_su">Nhân sự</option>
              <option value="chuc_vu">Chức vụ</option>
            </select>
            <select v-if="newChunk.category == 'phan_anh_kien_nghi'" v-model="newChunk.subject" class="filter-select">
              <option value="ha_tang">Hạ tầng</option>
              <option value="moi_truong">Môi trường</option>
              <option value="an_ninh_trat_tu">An ninh trật tự</option>
              <option value="do_thi">Đô thị</option>
              <option value="giao_thong">Giao thông</option>
              <option value="khieu_nai_to_cao">Khiếu nại tố cáo</option>
            </select>
          </div>
          <div v-else class="filter-group">
            <label>Subject:</label>
            
            <select v-if="newChunk.category == 'thong_tin_tong_quan'" v-model="newChunk.subject" class="filter-select">
              <option value="gioi_thieu_chung">Giới thiệu chung</option>
              <option value="chuc_nang_nhiem_vu">Chức năng nhiệm vụ</option>
              <option value="hoi_vien_doi_tuong_phuc_vu">Hội viên đối tượng phục vụ</option>
              <option value="hoat_dong_phong_trao">Hoạt động phong trào</option>
              <option value="chuong_trinh_ho_tro">Chương trình hỗ trợ</option>
              <option value="thu_tuc_quy_trinh">Thủ tục quy trình</option>
              <option value="quy_dinh_huong_dan">Quy định hướng dẫn</option>
              <option value="thong_tin_lien_he">Thông tin liên hệ</option>

            </select>
            <select v-if="newChunk.category == 'to_chuc_bo_may'" v-model="newChunk.subject" class="filter-select">
              <option value="nhan_su">Nhân sự</option>
              <option value="chuc_vu">Chức vụ</option>
            </select>
          </div>
          <div class="filter-group">
            <label>Phạm vi (scope):</label>
            <select v-model="newChunk.scope" class="filter-select">
              <option value="xa_phuong">Xã phường</option>
              <option value="tinh_thanh">Tỉnh thành</option>
              <option value="quoc_gia">Quốc gia</option>
            </select>
          </div>
        </div>

        <div class="modal-actions">
          <button class="btn-save" @click="submitCreateChunk" :disabled="isSaving">💾 Lưu</button>
          <button class="btn-cancel" @click="closeCreateModalChunk">Hủy</button>
        </div>

      </div>
    </div>

    <div v-if="isCreatePromptModalOpen" class="modal-overlay">
      <div class="modal-box">
        <h3>Tạo Prompt Mới</h3>

        <label>Prompt name</label>
        <input v-model="newPrompt.prompt_name" class="edit-input" />

        <label>Prompt type</label>
        <input v-model="newPrompt.prompt_type" class="edit-input" placeholder="vd: history_rewrite" />

        <label>Content</label>
        <textarea v-model="newPrompt.content" class="edit-input" rows="8"></textarea>

        <label>Description</label>
        <textarea v-model="newPrompt.description" class="edit-input" rows="3"></textarea>

        <div class="filter-group" style="padding: 0; background: transparent; border: 0;">
          <label style="min-width: 70px;">Version</label>
          <input v-model.number="newPrompt.version" class="edit-input" type="number" min="1" style="max-width: 120px;" />
          <label style="min-width: 80px;">Active</label>
          <input v-model="newPrompt.is_active" type="checkbox" />
        </div>

        <div class="modal-actions">
          <button class="btn-save" @click="submitCreatePrompt" :disabled="isSaving">💾 Lưu</button>
          <button class="btn-cancel" @click="closeCreatePromptModal">Hủy</button>
        </div>
      </div>
    </div>

    <div v-if="isEditPromptModalOpen" class="modal-overlay">
      <div class="modal-box prompt-edit-modal">
        <h3>Chỉnh sửa Prompt</h3>

        <label>Tên prompt</label>
        <input v-model="promptEditingData.prompt_name" class="edit-input" />

        <label>Prompt type</label>
        <input v-model="promptEditingData.prompt_type" class="edit-input" placeholder="vd: answer_QA" />

        <div class="prompt-edit-row">
          <div class="prompt-edit-col">
            <label>Version</label>
            <input v-model.number="promptEditingData.version" class="edit-input" type="number" min="1" />
          </div>
          <div class="prompt-edit-col">
            <label>Trạng thái</label>
            <div class="prompt-edit-switch-row">
              <input v-model="promptEditingData.is_active" type="checkbox" />
              <span>{{ promptEditingData.is_active ? 'Đang bật' : 'Đang tắt' }}</span>
            </div>
          </div>
        </div>

        <label>Nội dung prompt</label>
        <textarea v-model="promptEditingData.content" class="edit-input" rows="10"></textarea>

        <label>Mô tả</label>
        <textarea v-model="promptEditingData.description" class="edit-input" rows="3"></textarea>

        <div class="modal-actions">
          <button class="btn-save" @click="saveEditPrompt" :disabled="isSaving">💾 Lưu</button>
          <button class="btn-cancel" @click="cancelEditPrompt">Hủy</button>
        </div>
      </div>
    </div>
    <!-- Delete Confirm Modal -->
    <div v-if="isDeleteModalOpen" class="modal-overlay">
      <div class="modal-box">

        <h3>Xác nhận xóa</h3>
        <p style="font-size: 1.1em;">Bạn có chắc chắn muốn xóa alias này?</p>

        <div class="modal-actions">
          <button 
            class="btn-delete-confirm" 
            @click="confirmDeleteAlias"
            :disabled="isSaving"
          >
            🗑️ Xóa
          </button>

          <button 
            class="btn-cancel" 
            @click="closeDeleteModal"
          >
            Hủy
          </button>
        </div>

      </div>
    </div>

    <!-- Delete Confirm Modal -->
    <div v-if="isDeleteModalOpenChunk" class="modal-overlay">
      <div class="modal-box">

        <h3>Xác nhận xóa</h3>
        <p style="font-size: 1.1em;">Bạn có chắc chắn muốn xóa chunk này?</p>

        <div class="modal-actions">
          <button 
            class="btn-delete-confirm" 
            @click="confirmDeleteChunk"
            :disabled="isSaving"
          >
            🗑️ Xóa
          </button>

          <button 
            class="btn-cancel" 
            @click="closeDeleteModal"
          >
            Hủy
          </button>
        </div>

      </div>
    </div>
    
    <!-- Chunks Modal -->
    <div v-if="showChunksModal" class="modal-overlay">
      <div class="modal-box" style="max-width: 900px; max-height: 90vh; overflow-y: auto;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
          <h3 style="margin: 0;">Tài liệu tham khảo ({{ selectedMessageChunks.length }})</h3>
          <button 
            class="btn-cancel" 
            @click="showChunksModal = false"
            style="margin: 0;"
          >
            ✕ Đóng
          </button>
        </div>
        
        <div v-if="selectedMessageChunks.length === 0" style="text-align: center; color: #999; padding: 40px;">
          Không có tài liệu
        </div>
        
        <div v-for="(chunk, idx) in selectedMessageChunks" :key="chunk.id || idx" style="margin-bottom: 24px; padding: 16px; background: #f5f5f5; border-radius: 8px; border: 1px solid #ddd;">
          <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
            <h4 style="margin: 0; color: #333;">📄 Tài liệu {{ idx + 1 }}</h4>
            <div style="display: flex; align-items: center; gap: 8px;">
              <span v-if="chunk.confidence_score" style="background: #4ade80; color: white; padding: 4px 12px; border-radius: 4px; font-size: 0.9em;">
                Score: {{ (chunk.confidence_score * 100).toFixed(0) }}%
              </span>
              <button class="btn-view-chunks" @click="filterChunkFromReference(chunk)">
                Lọc chunk này
              </button>
            </div>
          </div>
          
          <div v-if="chunk.category" style="margin-bottom: 8px;">
            <span style="color: #666; font-size: 0.9em;">
              <strong>Category:</strong> {{ chunk.category }}
              <span v-if="chunk.subject" style="margin-left: 16px;"><strong>Subject:</strong> {{ chunk.subject }}</span>
            </span>
          </div>
          
          <div style="background: white; padding: 12px; border-radius: 4px; border: 1px solid #eee; color: #333; line-height: 1.6;">
            {{ chunk.text_content }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>

body{
  margin: 0;
}

.keywords-wrapper {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.keyword-badge {
  background: #e0e7ff;
  color: #3730a3;
  padding: 4px 10px;
  border-radius: 14px;
  font-size: 1em;
  display: flex;
  align-items: center;
  gap: 6px;
}

.keyword-remove-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.9em;
  color: #ef4444;
}

.keyword-remove-btn:hover {
  color: #000000;
}

.keyword-add-wrapper {
  margin-top: 10px;
  display: flex;
  gap: 8px;
}

.keyword-input {
  flex: 1;
  padding: 6px 10px;
  font-size: 0.95em;
  border-radius: 6px;
  border: 1px solid #6366f1;
}

.btn-add-keyword {
  background: #6366f1;
  color: white;
  border: none;
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
}

.btn-add-keyword:hover {
  background: #3134ee;
  transition-delay: 1ms;
}

.highlight {
  background-color: #fde047;
  padding: 2px 4px;
  border-radius: 4px;
}

.chunk-row-focused {
  background: rgba(59, 130, 246, 0.12);
}

/* special_contexts badges */
.sc-badge-group {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  justify-content: center;
}
.sc-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 1em;
  font-weight: 600;
  white-space: nowrap;
}
.sc-yeu_to_nuoc_ngoai           { background: #dbeafe; color: #1d4ed8; }
.sc-khu_vuc_bien_gioi           { background: #dcfce7; color: #15803d; }
.sc-da_co_ho_so_giay_to_ca_nhan { background: #fef9c3; color: #854d0e; }
.sc-uy_quyen                    { background: #fce7f3; color: #9d174d; }
.sc-chon_quoc_tich              { background: #ede9fe; color: #6d28d9; }
.sc-qua_han_dang_ky             { background: #fee2e2; color: #b91c1c; }
.sc-mat_so_ho_tich_va_ban_chinh { background: #ffedd5; color: #c2410c; }

.sc-editor {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 160px;
}
.sc-edit-tags {
  justify-content: flex-start;
  flex-wrap: wrap;
  gap: 4px;
}
.sc-remove-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.9em;
  line-height: 1;
  padding: 0 0 0 4px;
  color: inherit;
  opacity: 0.7;
}
.sc-remove-btn:hover {
  opacity: 1;
}
.sc-add-select {
  font-size: 0.8em;
  padding: 2px 4px;
}

.pa-badge {
  background: #fef3c7;
  color: #92400e;
}

/* Sidebar */
.sidebar {
  width: 306px;
  background: white;
  border-right: 1px solid #eee;
  padding: 20px;
  font-size: 1em;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 30px;
}

.logo-icon {
  font-size: 24px;
}

.logo-title {
  font-weight: 700;
  font-size: 16px;
}

.logo-sub {
  font-size: 12px;
  color: gray;
}

.menu-section {
  font-weight: 700;
  margin-bottom: 10px;
  font-size: 1em;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #6b7280;
}

.menu-item {
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 5px;
  font-size: 1.1em;
  font-weight: 500;
  margin: 8px 0;
}

.menu-item:hover {
  background: #f1f3f9;
}

.menu-item.active {
  background: #e8edff;
  color: #3b5bfd;
  font-weight: 600;
}

.tenant-active-box {
  margin-top: 18px;
  padding: 12px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fbff;
}

.tenant-active-label {
  font-size: 0.85em;
  color: #6b7280;
}

.tenant-active-code {
  margin-top: 4px;
  margin-bottom: 10px;
  font-weight: 600;
  color: #1f2937;
  word-break: break-word;
}

.tenant-clear-btn {
  width: 100%;
  padding: 8px 10px;
  border: none;
  border-radius: 6px;
  background: #ef4444;
  color: white;
  cursor: pointer;
  font-size: 0.9em;
}

.tenant-clear-btn:hover {
  background: #dc2626;
}

.chat-section {
  margin: 4px 2rem 2rem;
  min-height: 62vh;
  background: #f3f4f6;
  border-radius: 18px;
  box-shadow: 0 15px 35px rgba(0,0,0,0.12);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  width: 100%;
  margin-bottom: 0;
  max-height: 96vh;
}

/* Header */
.chat-header {
  background: linear-gradient(135deg, #6366f1, #9333ea);
  color: white;
  padding: 14px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chat-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}

.dot {
  width: 8px;
  height: 8px;
  background: #22c55e;
  border-radius: 50%;
}

.close-btn {
  background: none;
  border: none;
  color: white;
  font-size: 16px;
  cursor: pointer;
}

/* Body */
.chat-body {
  flex: 1;
  padding: 16px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.bot-message, .user-message {
  padding: 0;
  margin: 6px 0;
  max-width: 80%;
  font-size: 1em;
  white-space: normal;
  font-family: "ui-sans-serif", "-apple-system", "system-ui", "Segoe UI", "Helvetica", "Apple Color Emoji", "Arial", "sans-serif", "Segoe UI Emoji", "Segoe UI Symbol";
}

.message-bubble {
  padding: 4px 16px;
  border-radius: 18px;
  border: 1px solid #d1d5db;
  box-shadow: 0 2px 6px rgba(0,0,0,0.04);
}

.message-time {
  margin-top: 4px;
  font-size: 0.8em;
  color: #6b7280;
  padding: 0 4px;
}

.bot-message {
  align-self: flex-start;
}

.bot-message .message-bubble {
  background: #f3f4f6;
}

.user-message {
  align-self: flex-end;
}

.user-message .message-bubble {
  background: #e0e7ff;
  border-color: #c7d2fe;
}

.user-message .message-time {
  text-align: right;
}

/* Footer */
.chat-footer {
  padding: 12px;
  background: white;
  display: flex;
  gap: 8px;
  border-top: 1px solid #e5e7eb;
}

.chat-footer input {
  flex: 1;
  padding: 14px 12px;
  border-radius: 12px;
  border: 1px solid #d1d5db;
  outline: none;
  font-size: 0.95em;
}

.chat-footer input:focus {
  border-color: #6366f1;
}

.chat-footer button {
  width: 46px;
  border-radius: 100%;
  border: none;
  background: linear-gradient(135deg, #6366f1, #9333ea);
  color: white;
  cursor: pointer;
}

.chat-footer button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.data-table {
  flex: 1;
  margin: 2rem;
  background: white;
  border-radius: 14px;
  box-shadow: 0 8px 20px rgba(0,0,0,0.06);
  overflow: auto;
  height: 58vh;
  display: flex;
  flex-direction: column;
}

.data-table table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}

/* Header */
.data-table thead {
  background: #f9fafb;
}

.data-table th {
  text-align: center;
  padding: 14px 16px;
  font-size: 1em;
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 1px solid #e5e7eb;
}

/* Body */
.data-table td {
  padding: 16px;
  border-bottom: 1px solid #f1f5f9;
  font-size: 1em;
  color: #1f2937;
  vertical-align: top;
}

.data-table tr:hover {
  background: #f9fafb;
}

/* Column width control */
.col-index {
  width: 40px;
  text-align: center;
  font-weight: 600;
  color: #6b7280;
}

.col-content {
  width: 70%;
}

.col-scope {
  width: 80px;
  text-align: center;
}

/* when chat is open reserve space on right so table isn't covered */
/* .data-table.with-chat {
  margin-right: 380px;
} */

/* Data chunks table - similar to data-table */
.data-chunks-table {
  flex: 1;
  margin: 2rem;
  background: white;
  border-radius: 14px;
  box-shadow: 0 8px 20px rgba(0,0,0,0.06);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  height: 92vh;
  margin-left: 3.2rem;
  margin-bottom: 1rem;
}

/* Filter Section */
.filter-section {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  background: #f9fafb;
  border-bottom: 1px solid #e5e7eb;
  flex-wrap: wrap;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-group label {
  font-weight: 600;
  color: #4b5563;
  min-width: 80px;
  font-size: 0.95em;
}

.filter-select {
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: white;
  color: #1f2937;
  cursor: pointer;
  font-size: 0.95em;
  transition: all 200ms;
  min-width: 150px;
}

.filter-select:hover {
  border-color: #6366f1;
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.1);
}

.filter-select:focus {
  outline: none;
  border-color: #6366f1;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.btn-reset-filter {
  padding: 8px 14px;
  background: #ef4444;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
  font-size: 0.95em;
  transition: all 200ms;
  margin-left: auto;
}

.btn-reset-filter:hover {
  background: #dc2626;
  box-shadow: 0 4px 12px rgba(239, 68, 68, 0.3);
}

.filter-result {
  padding: 8px 16px;
  background: #f0f4ff;
  border-bottom: 1px solid #e5e7eb;
  color: #3b5bfd;
  font-size: 0.9em;
  font-weight: 500;
}

.data-chunks-table table {
  width: 100%;
  border-collapse: collapse;
  table-layout: auto;
  min-width: 1700px; /* tăng chút cho đủ chỗ */
}

.col-question {
  min-width: 350px;
  width: 350px;
}

.col-reason {
  min-width: 500px;
  width: 500px;
}

.data-chunks-table thead {
  background: #f9fafb;
}

.data-chunks-table th {
  text-align: center;
  padding: 14px 16px;
  font-size: 1em;
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 1px solid #e5e7eb;
}

.data-chunks-table td {
  padding: 16px;
  padding-left: 36px;
  border-bottom: 1px solid #f1f5f9;
  font-size: 1.1em;
  color: #1f2937;
  vertical-align: top;
}

.data-chunks-table tr:hover {
  background: #f9fafb;
}

/* .data-chunks-table.with-chat {
  margin-right: 380px;
} */

/* Content text */
.content-text {
  line-height: 1.5;
  word-break: break-word;
  /* allow full text to display */
  display: block;
  overflow: visible;
  white-space: pre-line;
}

/* Scope badge */
.badge {
  display: inline-block;
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 1em;
  font-weight: 500;
  background: #e0e7ff;
  color: #3730a3;
}

.action-cell {
  min-width: 100px;
}

.action-buttons {
  display: flex;
  gap: 8px;
  justify-content: center;
}

.btn-create {
    padding: 8px 14px;
    background: #000000;
    color: white;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-weight: 500;
    font-size: 0.95em;
    transition: all 200ms;
    margin-right: 26px;
}

.btn-edit, .btn-save, .btn-cancel {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 18px;
  padding: 4px 8px;
  border-radius: 4px;
  transition: background 200ms;
}

.btn-edit:hover {
  background: #e0e7ff;
}

.btn-save {
  color: #22c55e;
}

.btn-save:hover:not(:disabled) {
  background: #dcfce7;
}

.btn-save:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-cancel {
  color: #ef4444;
}

.btn-cancel:hover {
  background: #fee2e2;
}

.edit-input-wrapper {
  width: 100%;
}

.edit-input {
  width: 100%;
  padding: 8px;
  border: 1px solid #6366f1;
  border-radius: 4px;
  font-size: 1em;
  font-family: inherit;
  box-sizing: border-box;
  resize: none;
  overflow-y: auto;
}

textarea.edit-input {
  min-height: 60px;
  line-height: 1.5;
  max-height: 300px;
}

.edit-input:focus {
  outline: none;
  border-color: #3b5bfd;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.edit-select {
  cursor: pointer;
  appearance: none;
  background: white url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%236366f1' d='M6 9L1 4h10z'/%3E%3C/svg%3E") no-repeat right 8px center;
  padding-right: 28px;
}

.edit-select:focus {
  outline: none;
  border-color: #3b5bfd;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.edit-select option {
  padding: 6px 8px;
  border-radius: 4px;
  margin: 2px;
}

.edit-select option:nth-child(1) {
  background-color: #f3f4f6;
  color: #6b7280;
}

.edit-select option:nth-child(2) {
  background: linear-gradient(135deg, #dbeafe, #bfdbfe);
  color: #1e3a8a;
  font-weight: 500;
}

.edit-select option:nth-child(3) {
  background: linear-gradient(135deg, #dcfce7, #bbf7d0);
  color: #15803d;
  font-weight: 500;
}

.edit-select option:nth-child(4) {
  background: linear-gradient(135deg, #fed7aa, #fdba74);
  color: #92400e;
  font-weight: 500;
}

.edit-select option:nth-child(5) {
  background: linear-gradient(135deg, #fbcfe8, #f9a8d4);
  color: #831843;
  font-weight: 500;
}

.edit-select option:nth-child(6) {
  background: linear-gradient(135deg, #e9d5ff, #d8b4fe);
  color: #581c87;
  font-weight: 500;
}

.edit-select option:nth-child(7) {
  background: linear-gradient(135deg, #fef3c7, #fde68a);
  color: #78350f;
  font-weight: 500;
}

.edit-select option:nth-child(8) {
  background: linear-gradient(135deg, #f5d4ff, #f0abfc);
  color: #6b21a8;
  font-weight: 500;
}

.edit-select option:checked {
  background: linear-gradient(135deg, #e0e7ff, #c7d2fe);
  color: #1e1b4b;
  font-weight: 600;
}
.search-box {
  margin: 20px 0;
  display: flex;
  justify-content: space-between;
  align-items: center;

}

.search-box input {
  width: 36%;
  padding: 10px 14px;
  margin-left: 18px;
  border-radius: 8px;
  font-size: 1em;
  border: 1px solid #ddd;
}

.search-box input:focus{
  border-color: #6366f1;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.4);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 2000;
}

.modal-box {
  background: white;
  padding: 24px;
  border-radius: 12px;
  width: 500px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.modal-box h3 {
  margin-bottom: 10px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 10px;
}

.autocomplete-wrapper {
  position: relative;
}

.autocomplete-dropdown {
  position: absolute;
  width: 100%;
  max-height: 260px;
  overflow-y: auto;
  background: white;
  border: 1px solid #ddd;
  border-radius: 8px;
  margin-top: 4px;
  z-index: 3000;
  box-shadow: 0 8px 20px rgba(0,0,0,0.15);
}

.autocomplete-item {
  padding: 10px 12px;
  cursor: pointer;
  font-size: 0.95em;
}

.autocomplete-item:hover {
  background: #f3f4f6;
}

.btn-delete-confirm {
  background: #ef4444;
  color: white;
  padding: 8px 14px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.btn-delete-confirm:hover {
  background: #dc2626;
}

/* .log-panel {
  position: fixed;
  bottom: 12px;
  width: 40%;
  margin-top: 16px;
  background: #111827;
  border-radius: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  height: 200px;
  border-top: 2px solid #1f2937;
  margin-left: 26px;
} */

.log-panel {
  position: fixed;
  bottom: 14px;
  left: 426px;
  width: 588px;
  height: 228px;
  background: #111827;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  z-index: 2000;
  cursor: default;
  border-top: 2px solid #1f2937;
}

.log-header {
  background: #1f2937;
  color: white;
  padding: 8px 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.9em;
  border-radius: 12px;
  cursor: pointer;
}

.log-header button {
  background: none;
  border: 1px solid #374151;
  color: white;
  padding: 4px 8px;
  border-radius: 6px;
  cursor: pointer;
}

.log-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;
  font-family: monospace;
  font-size: 0.85em;
  color: #d1d5db;
}

.log-item {
  margin-bottom: 4px;
}

.log-item.info {
  color: #60a5fa;
  font-size: 1.3em;
}

.log-item.warn {
  color: #fbbf24;
}

.log-item.error {
  color: #f87171;
}
.table-wrapper {
  flex: 1;
  overflow-y: auto;
}

.table-scroll {
  flex: 1;
  overflow-x: auto;   /* QUAN TRỌNG */
  overflow-y: auto;
}

.table-scroll table {
  min-width: 1600px;
  border-collapse: collapse;
}

/* Giữ header dính trên */
.table-scroll thead th {
  position: sticky;
  top: 0;
  background: #f9fafb;   /* bắt buộc có background */
  z-index: 5;
}

.noted {
  background: #fff3a3 !important;
}

.btn-note {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 16px;
}

.btn-note:hover {
  transform: scale(1.2);
}

.message-markdown {
  line-height: 1.6;
  word-break: break-word;
}

.btn-view-chunks {
  margin-top: 12px;
  padding: 8px 16px;
  background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.95em;
  font-weight: 500;
  transition: all 0.2s ease;
  display: inline-block;
}

.btn-view-chunks:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3);
}

.btn-view-chunks:active {
  transform: translateY(0);
}

.message-markdown p {
  margin: 0 0 10px;
}

.message-markdown p:last-child {
  margin-bottom: 0;
}

.message-markdown ul,
.message-markdown ol {
  margin: 8px 0 8px 20px;
  padding: 0;
}

.message-markdown li {
  margin: 4px 0;
}

.message-markdown strong {
  font-weight: 600;
}

.message-markdown em {
  font-style: italic;
}

.message-markdown h1,
.message-markdown h2,
.message-markdown h3,
.message-markdown h4 {
  margin: 10px 0 8px;
  font-size: 1em;
  font-weight: 700;
}

.message-markdown code {
  background: rgba(0, 0, 0, 0.06);
  padding: 2px 6px;
  border-radius: 6px;
  font-size: 0.95em;
}

.message-markdown pre {
  background: #f6f8fa;
  padding: 10px 12px;
  border-radius: 10px;
  overflow-x: auto;
  margin: 8px 0;
}

.message-markdown pre code {
  background: transparent;
  padding: 0;
}

.message-markdown blockquote {
  margin: 8px 0;
  padding-left: 12px;
  border-left: 3px solid #d1d5db;
  color: #4b5563;
}

.thought-toggle {
  margin-bottom: 8px;
  border: none;
  background: #f3f4f6;
  color: #374151;
  padding: 6px 10px;
  border-radius: 8px;
  font-size: 0.82em;
  cursor: pointer;
}

.thought-toggle:hover {
  background: #e5e7eb;
  margin-top: 10px;
}

.thought-box {
  background: #eef2ff;
  border: 1px solid #c7d2fe;
  border-radius: 10px;
  padding: 8px 10px;
  margin-bottom: 10px;
}

.thought-item {
  font-size: 0.82em;
  color: #3730a3;
  line-height: 1.45;
  margin-bottom: 4px;
}

.thought-item:last-child {
  margin-bottom: 0;
}

.thinking-state {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  margin: 4px 0;
}

.thinking-bubble {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-radius: 14px;
  background: #f3f4f6;
  border: 1px solid #e5e7eb;
}

.thinking-bubble span {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #6b7280;
  animation: dotWave 1s infinite ease-in-out;
}

.thinking-bubble span:nth-child(2) {
  animation-delay: 0.12s;
}

.thinking-bubble span:nth-child(3) {
  animation-delay: 0.24s;
}

.thinking-label {
  color: #6b7280;
  font-size: 0.9em;
  padding-left: 4px;
}

.thinking-thought-line {
  max-width: 100%;
  color: #4b5563;
  font-size: 0.84em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-left: 4px;
  min-height: 1.25em;
  transition: opacity 180ms ease;
}

@keyframes dotWave {
  0%, 60%, 100% {
    transform: translateY(0);
    opacity: 0.45;
  }
  30% {
    transform: translateY(-5px);
    opacity: 1;
  }
}

.message-markdown table {
  width: 100%;
  border-collapse: collapse;
  margin: 10px 0;
  font-size: 0.95em;
}

.message-markdown th,
.message-markdown td {
  border: 1px solid #e5e7eb;
  padding: 8px 10px;
  text-align: left;
}

.message-markdown th {
  background: #f9fafb;
}

.prompt-cards {
  padding: 12px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-top: 25px;
}

.prompt-empty {
  text-align: center;
  color: #6b7280;
  padding: 24px;
}

.prompt-card {
  border: 1px solid #d1d5db;
  border-radius: 14px;
  background: #f9fafb;
  padding: 16px 20px;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.08);
  margin: 1px 59px;
  padding: 33px 39px;
}

.prompt-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.prompt-title-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  min-width: 0;
}

.prompt-title {
  font-size: 1.4em;
  font-weight: 700;
  margin: 0;
  color: #111827;
}

.prompt-chip {
  background: #dbeafe;
  color: #1d4ed8;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 1em;
  font-weight: 600;
}

.prompt-chip-muted {
  background: #e5e7eb;
  color: #4b5563;
}

.prompt-card-body {
  margin-top: 12px;
}

.prompt-content-text {
  margin: 0;
  color: #374151;
  font-size: 1.2em;
  line-height: 1.55;
  white-space: normal;
  display: -webkit-box;
  line-clamp: 2;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  padding-right: 110px;
}

.prompt-card-desc {
  margin-top: 10px;
}

.prompt-desc-text {
  margin: 0;
  color: #6b7280;
  font-size: 1.05em;
}

.prompt-card-foot {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid #d1d5db;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.prompt-edit-modal {
  width: min(860px, 92vw);
  max-height: 90vh;
  overflow-y: auto;
}

.prompt-edit-row {
  display: flex;
  gap: 12px;
}

.prompt-edit-col {
  flex: 1;
}

.prompt-edit-switch-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 38px;
}

.prompt-time {
  color: #6b7280;
  font-size: 1em;
}

.prompt-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.prompt-action-btn {
  border: 1px solid #cbd5e1;
  background: #ffffff;
  color: #111827;
  padding: 6px 12px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 1.05em;
  font-weight: 600;
}

.prompt-action-btn:hover {
  background: #f3f4f6;
}

.prompt-action-btn-danger {
  color: #dc2626;
  border-color: #fecaca;
}

.prompt-toggle {
  width: 56px;
  height: 32px;
  border: none;
  border-radius: 999px;
  background: #d1d5db;
  display: inline-flex;
  align-items: center;
  padding: 4px;
  cursor: pointer;
  transition: background 0.2s ease;
}

.prompt-toggle.active {
  background: #16a34a;
}

.prompt-toggle-knob {
  width: 24px;
  height: 24px;
  border-radius: 999px;
  background: #ffffff;
  transition: transform 0.2s ease;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.25);
}

.prompt-toggle.active .prompt-toggle-knob {
  transform: translateX(24px);
}
</style>