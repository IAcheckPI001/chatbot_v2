<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount , watch, nextTick } from 'vue'

const API_BASE_URL = '/api'
// const API_BASE_URL = 'http://localhost:5000/api'
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
const chunkSearch = ref('')
const showChunkDropdown = ref(false)
const isDeleteModalOpen = ref(false)
const isSaving = ref(false)
const deleteTargetId = ref<string | null>(null)
const chatBody = ref<HTMLElement | null>(null)
const isLLMEnabled = ref(false) // mặc định bật
const showSettings = ref(false)
const settingsRef = ref<HTMLElement | null>(null)
// const sessionId = crypto.randomUUID()
const originalData = ref<any>(null)


// đóng khi click ngoài
function handleClickOutside(event: MouseEvent) {
  if (
    settingsRef.value &&
    !settingsRef.value.contains(event.target as Node)
  ) {
    showSettings.value = false
  }
}

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
  tenant_name: 'xa_ba_diem',
  scope: 'xa',
  text_content: '',
  procedure_name: null,
  category: null,
  subject: null,
})

function openDeleteModal(id: string) {
  deleteTargetId.value = id
  isDeleteModalOpen.value = true
}

function closeDeleteModal() {
  deleteTargetId.value = null
  isDeleteModalOpen.value = false
}

const filteredChunksForSelect = computed(() => {
  if (!chunkSearch.value) return chunksData.value

  return chunksData.value.filter(chunk =>
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

// chat messages shown in widget
const messages = ref<Array<{text: string; from: 'user' | 'bot'}>>([
  { text: 'Xin chào! Tôi là trợ lý AI của UBND Phường.', from: 'bot' }
])

function scrollToBottom() {
  if (chatBody.value) {
    chatBody.value.scrollTop = chatBody.value.scrollHeight
  }
}
watch(messages, async () => {
  await nextTick()
  scrollToBottom()
}, { deep: true })

function getSessionId() {
  let sessionId = localStorage.getItem("chat_session_id")

  if (!sessionId) {
    sessionId = crypto.randomUUID()
    localStorage.setItem("chat_session_id", sessionId)
  }

  return sessionId
}

async function sendMessage() {
  if (!userInput.value.trim()) return
  const text = userInput.value.trim()
  const sessionId = getSessionId()
  // push user message
  messages.value.push({ text, from: 'user' })
  userInput.value = ''
  
  // clear table data
  responses.value = []
  
  // switch to test section to show data-table
  activeSection.value = 'test'
  
  // call backend API
  loadingChat.value = true
  apiError.value = ''
  clearLogs();
  try {
    const res = await fetch(`${API_BASE_URL}/chat-stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, session_id: sessionId, use_llm: isLLMEnabled.value, chunk_limit: chunkLimit.value })
    })

    const reader = res.body!.getReader()
    const decoder = new TextDecoder()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const chunk = decoder.decode(value)
      const lines = chunk.split('\n\n')

      lines.forEach(line => {
        if (line.startsWith('data: ')) {
          const data = JSON.parse(line.replace('data: ', ''))

          if (data.log) {
            addLog(data.log)
          }

          if (data.chunks) {
            let botReply = data.replies
            messages.value.push({ text: botReply, from: 'bot' })
            // update table with all returned responses
            responses.value = data.chunks || []
          }
        }
      })
    }
  } catch (error: any) {
    apiError.value = `Connection error: ${error.message}`
    messages.value.push({ text: 'Xin lỗi, có lỗi khi kết nối đến server.', from: 'bot' })
  } finally {
    loadingChat.value = false
    loadLogs(true)
  }
}

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
const categoryFilter = ref<string>('')
const subjectFilter = ref<string>('')
const typeLogFilter = ref<string>('')
const editingId = ref<string | null>(null)
const editingData = ref<any>(null)
const activeSection = ref("chunks");
const searchKeyword = ref('')

const filteredChunks = computed(() => {
  return chunksData.value.filter(item => {
    const categoryMatch = !categoryFilter.value || item.category === categoryFilter.value
    const subjectMatch = !subjectFilter.value || item.subject === subjectFilter.value
    
    const keywordMatch =
      !searchKeyword.value ||
      item.text_content
        ?.toLowerCase()
        .includes(searchKeyword.value.toLowerCase())

    return categoryMatch && subjectMatch && keywordMatch
  })
})

const filteredAlias = computed(() => {
  return aliasData.value.filter(item => {

    const keywordMatch =
      !searchKeyword.value ||
      item.alias_text
        ?.toLowerCase()
        .includes(searchKeyword.value.toLowerCase())

    return keywordMatch
  })
})


const filteredLog = computed(() => {
  return logsData.value.filter(item => {
    const typeLogMatch = !typeLogFilter.value || item.event_type === typeLogFilter.value

    const keywordMatch =
      !searchKeyword.value ||
      item.raw_query
        ?.toLowerCase()
        .includes(searchKeyword.value.toLowerCase())

    return typeLogMatch && keywordMatch
  })
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
  if ($load || logsData.value.length === 0){
    try {
      const response = await fetch(`${API_BASE_URL}/get-logs`, {
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


const viewChunks = () => {
  activeSection.value = 'chunks';
  loadChunks(false);
};

const viewAlias = () => {
  activeSection.value = 'alias';
  loadAlias(false);
};

const viewLogs = () => {
  activeSection.value = 'log';
  loadLogs(false);
};

function startEdit(item: any) {
  originalData.value = { ...item }
  editingId.value = item.id
  editingData.value = { ...item,
    keywords: item.keywords ? [...item.keywords] : []
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
  if (!newChunk.value.text_content || !newChunk.value.tenant_name) {
    alert('Vui lòng nhập đủ thông tin')
    return
  }

  isSaving.value = true

  try {
    const response = await fetch(`${API_BASE_URL}/create-chunk`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newChunk.value)
    })

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`)
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
    tenant_name: 'xa_ba_diem',
    scope: 'xa',
    text_content: '',
    procedure_name: null,
    category: null,
    subject: null,
  }
}

const isChanged = computed(() => {
  if (!originalData.value) return false

  return (
    editingData.value.text_content !== originalData.value.text_content ||
    editingData.value.category !== originalData.value.category ||
    editingData.value.subject !== originalData.value.subject
  )
})

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
      body: JSON.stringify({ session_id: sessionId })
    })
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`)
    }

    const data = await response.json()
    console.log('Logs data:', data)

    const historyMessages = data.logs.flatMap((item:any) => [
      { text: item.raw_query, from: 'user' },
      { text: item.answer, from: 'bot' }
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
    </div>
    <section class="data-chunks-table" v-if="activeSection === 'alias'" :class="{ 'with-chat': isOpen }">
      <!-- Search -->
      <div class="search-box">
        <input 
          v-model="searchKeyword"
          type="text" 
          placeholder="Tìm kiếm alias text..." 
        />
        <button class="btn-create" @click="isCreateModalOpen = true" style="display: flex;">
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
            <option value="complaint">complaint</option>
            <option value="out_of_scope">out_of_scope</option>
            <option value="low_confidence">low_confidence</option>
            
          </select>
        <button class="btn-reset-filter" @click="typeLogFilter = '';">Xóa bộ lọc</button>
      </div>
      <div class="filter-result">Tìm thấy {{ filteredLog.length }} / {{ filteredLog.length }} kết quả</div>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th class="col-index">ID</th>
              <th class="col-question">Câu hỏi</th>
              <th class="col-question">Câu hỏi đã chuẩn hóa</th>
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
            <tr v-for="(item, idx) in filteredLog" :key="idx">
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
        <button class="btn-create" @click="isCreateChunkModalOpen = true" style="display: flex;">
          <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-plus w-4 h-4"><path d="M5 12h14"></path><path d="M12 5v14"></path></svg>
          <span style="font-size: 0.95em; margin-top: 2.2px; margin-left: 10px;">Tạo chunk</span>
        </button>
      </div>
      <!-- Filter Section -->
      <div class="filter-section">
        <div class="filter-group">
          <label>Category:</label>
          <select v-model="categoryFilter" class="filter-select">
            <option value="">Tất cả</option>
            <option value="thong_tin_tong_quan">thong_tin_tong_quan</option>
            <option value="to_chuc_bo_may">to_chuc_bo_may</option>
            <option value="thu_tuc_hanh_chinh">thu_tuc_hanh_chinh</option>
          </select>
        </div>
        <div class="filter-group">
          <label>Subject:</label>
          <select v-if="categoryFilter == 'thu_tuc_hanh_chinh'" v-model="subjectFilter" class="filter-select">
            <option value="">Tất cả</option>
            <option value="tu_phap_ho_tich">tu_phap_ho_tich</option>
            <option value="doanh_nghiep">doanh_nghiep</option>
            <option value="giao_thong_van_tai">giao_thong_van_tai</option>
            <option value="dat_dai">dat_dai</option>
            <option value="xay_dung_nha_o">xay_dung_nha_o</option>
            <option value="dau_tu">dau_tu</option>
            
            <option value="lao_dong_viec_lam">lao_dong_viec_lam</option>
            <option value="bao_hiem_an_sinh">bao_hiem_an_sinh</option>
            <option value="giao_duc_dao_tao">giao_duc_dao_tao</option>
            <option value="y_te">y_te</option>
            <option value="tai_nguyen_moi_truong">tai_nguyen_moi_truong</option>
            <option value="van_hoa_the_thao_du_lich">van_hoa_the_thao_du_lich</option>
            
            <option value="khoa_hoc_cong_nghe">khoa_hoc_cong_nghe</option>
            <option value="thong_tin_truyen_thong">thong_tin_truyen_thong</option>
            <option value="nong_nghiep">nong_nghiep</option>
            <option value="cong_thuong">cong_thuong</option>
            <option value="tai_chinh_thue_phi">tai_chinh_thue_phi</option>
          </select>
          <select v-if="categoryFilter == 'thong_tin_tong_quan'" v-model="subjectFilter" class="filter-select">
            <option value="">Tất cả</option>
            <option value="thong_tin_khu_pho">thong_tin_khu_pho</option>
            <option value="lich_lam_viec">lich_lam_viec</option>
            <option value="thong_tin_lien_he">thong_tin_lien_he</option>
            <option value="tong_quan">tong_quan</option>
          </select>
          <select v-if="categoryFilter == 'to_chuc_bo_may'" v-model="subjectFilter" class="filter-select">
            <option value="">Tất cả</option>
            <option value="nhan_su">nhan_su</option>
            <option value="chuc_vu">chuc_vu</option>
          </select>
        </div>
        <button class="btn-reset-filter" @click="categoryFilter = ''; subjectFilter = ''">Xóa bộ lọc</button>
      </div>
      <div class="filter-result">Tìm thấy {{ filteredChunks.length }} / {{ chunksData.length }} kết quả</div>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th class="col-index">ID</th>
              <th class="col-content">Text Content</th>
              <th class="col-index">Category</th>
              <th class="col-index">Subject</th>
              <!-- <th class="col-index">Keywords</th> -->
              <th class="col-index">Actions</th>
            </tr>
          </thead>

          <tbody>
            <tr v-if="chunksData.length === 0">
              <td colspan="5" style="text-align: center; padding: 20px; color: #999;">
                {{ isLoading ? 'Đang tải...' : 'Không có dữ liệu' }}
              </td>
            </tr>
            <tr v-for="(item, idx) in filteredChunks" :key="idx">
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
                    <option value="thong_tin_tong_quan">thong_tin_tong_quan</option>
                    <option value="to_chuc_bo_may">to_chuc_bo_may</option>
                    <option value="thu_tuc_hanh_chinh">thu_tuc_hanh_chinh</option>
                  </select>
                </div>
                <span v-else>{{ item.category || '-' }}</span>
              </td>
              <td class="col-index">
                <div v-if="editingId === item.id">
                    <div v-if="item.category === 'thu_tuc_hanh_chinh'" class="edit-input-wrapper">
                      <select v-model="editingData.subject" class="edit-input edit-select">
                        <option value="">-- Chọn --</option>
                        <option value="tu_phap_ho_tich">tu_phap_ho_tich</option>
                        <option value="doanh_nghiep">doanh_nghiep</option>
                        <option value="giao_thong_van_tai">giao_thong_van_tai</option>
                        <option value="dat_dai">dat_dai</option>
                        <option value="xay_dung_nha_o">xay_dung_nha_o</option>
                        <option value="dau_tu">dau_tu</option>
                        
                        <option value="lao_dong_viec_lam">lao_dong_viec_lam</option>
                        <option value="bao_hiem_an_sinh">bao_hiem_an_sinh</option>
                        <option value="giao_duc_dao_tao">giao_duc_dao_tao</option>
                        <option value="y_te">y_te</option>
                        <option value="tai_nguyen_moi_truong">tai_nguyen_moi_truong</option>
                        <option value="van_hoa_the_thao_du_lich">van_hoa_the_thao_du_lich</option>
                        
                        <option value="khoa_hoc_cong_nghe">khoa_hoc_cong_nghe</option>
                        <option value="thong_tin_truyen_thong">thong_tin_truyen_thong</option>
                        <option value="nong_nghiep">nong_nghiep</option>
                        <option value="cong_thuong">cong_thuong</option>
                        <option value="tai_chinh_thue_phi">tai_chinh_thue_phi</option>
                      </select>
                    </div>
                    <div v-if="item.category === 'thong_tin_tong_quan'" class="edit-input-wrapper">
                      <select v-model="editingData.subject" class="edit-input edit-select">
                        <option value="">-- Chọn --</option>
                        <option value="thong_tin_khu_pho">thong_tin_khu_pho</option>
                        <option value="lich_lam_viec">lich_lam_viec</option>
                        <option value="thong_tin_lien_he">thong_tin_lien_he</option>
                        <option value="tong_quan">tong_quan</option>
                      </select>
                    </div>
                    <div v-if="item.category === 'to_chuc_bo_may'" class="edit-input-wrapper">
                      <select v-model="editingData.subject" class="edit-input edit-select">
                        <option value="">-- Chọn --</option>
                        <option value="nhan_su">nhan_su</option>
                        <option value="chuc_vu">chuc_vu</option>
                      </select>
                    </div>
                </div>
                <span v-else>{{ item.subject || '-' }}</span>
              </td>
              <td class="col-index action-cell">
                <div v-if="editingId === item.id" class="action-buttons">
                  <button class="btn-save" @click="saveEditChunk()" :disabled="isSaving">💾</button>
                  <button class="btn-cancel" @click="cancelEdit()">❌</button>
                </div>
                <div v-else class="action-buttons">
                  <button class="btn-edit" @click="startEdit(item)">✏️</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
    <!-- Floating Button -->
    <!-- <section class="chat-toggle" @click="isOpen = !isOpen">
      💬
    </section> -->

    <!-- Chat Window -->
    <div v-if="isOpen = true" class="chat-widget">
      <!-- Header -->
      <div class="chat-header">
        <div class="chat-title">
          <span class="dot"></span>
          Chatbot 1.0
        </div>
        <!-- ⚙ Setting button -->
    <!-- Dropdown -->
    <div v-if="showSettings = true" class="settings-dropdown">
      
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
        <button class="close-btn" @click="isOpen = false">✕</button>
      </div>

      <!-- Messages -->
      <div 
        class="chat-body"
        ref="chatBody"
      >
        <div 
          v-for="(msg, idx) in messages" 
          :key="idx" 
          :class="msg.from + '-message'"
        >
          {{ msg.text }}
        </div>
      </div>

      <!-- Input -->
      <div class="chat-footer">
        <input
          v-model="userInput"
          placeholder="Nhập câu hỏi của bạn..."
          @keyup.enter="sendMessage"
        />
        <button @click="sendMessage" :disabled="loadingChat">{{ loadingChat ? '⏳' : '➤' }}</button>
      </div>
    </div>
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
        <div v-if="newChunk.category == 'thu_tuc_hanh_chinh'" style="display: flex; flex-direction: column;">
          <label style="font-size: 1.2em; margin-bottom: 16px;">Tên thủ tục (Nếu có)</label>
          <textarea 
            v-model="newChunk.procedure_name" 
            class="edit-input" style="font-size: 1.2em;"
          ></textarea>
        </div>
        <label style="font-size: 1.2em;">Nội dung chunk</label>
        <textarea 
          v-model="newChunk.text_content" 
          class="edit-input" style="min-height: 218px; font-size: 1.2em;"
        ></textarea>
        <div class="filter-section">
          <div class="filter-group">
            <label>Category:</label>
            <select v-model="newChunk.category" class="filter-select">
              <option value="thong_tin_tong_quan">thong_tin_tong_quan</option>
              <option value="to_chuc_bo_may">to_chuc_bo_may</option>
              <option value="thu_tuc_hanh_chinh">thu_tuc_hanh_chinh</option>
            </select>
          </div>
          <div class="filter-group">
            <label>Subject:</label>
            <select v-if="newChunk.category == 'thu_tuc_hanh_chinh'" v-model="newChunk.subject" class="filter-select">
              <option value="">-</option>
              <option value="tu_phap_ho_tich">tu_phap_ho_tich</option>
              <option value="doanh_nghiep">doanh_nghiep</option>
              <option value="giao_thong_van_tai">giao_thong_van_tai</option>
              <option value="dat_dai">dat_dai</option>
              <option value="xay_dung_nha_o">xay_dung_nha_o</option>
              <option value="dau_tu">dau_tu</option>
              
              <option value="lao_dong_viec_lam">lao_dong_viec_lam</option>
              <option value="bao_hiem_an_sinh">bao_hiem_an_sinh</option>
              <option value="giao_duc_dao_tao">giao_duc_dao_tao</option>
              <option value="y_te">y_te</option>
              <option value="tai_nguyen_moi_truong">tai_nguyen_moi_truong</option>
              <option value="van_hoa_the_thao_du_lich">van_hoa_the_thao_du_lich</option>
              
              <option value="khoa_hoc_cong_nghe">khoa_hoc_cong_nghe</option>
              <option value="thong_tin_truyen_thong">thong_tin_truyen_thong</option>
              <option value="nong_nghiep">nong_nghiep</option>
              <option value="cong_thuong">cong_thuong</option>
              <option value="tai_chinh_thue_phi">tai_chinh_thue_phi</option>
            </select>
            <select v-if="newChunk.category == 'thong_tin_tong_quan'" v-model="newChunk.subject" class="filter-select">
              <option value="tong_quan">tong_quan</option>
              <option value="thong_tin_khu_pho">thong_tin_khu_pho</option>
              <option value="lich_lam_viec">lich_lam_viec</option>
              <option value="thong_tin_lien_he">thong_tin_lien_he</option>
            </select>
            <select v-if="newChunk.category == 'to_chuc_bo_may'" v-model="newChunk.subject" class="filter-select">
              <option value="nhan_su">nhan_su</option>
              <option value="chuc_vu">chuc_vu</option>
            </select>
          </div>
        </div>

        <div class="modal-actions">
          <button class="btn-save" @click="submitCreateChunk" :disabled="isSaving">💾 Lưu</button>
          <button class="btn-cancel" @click="closeCreateModalChunk">Hủy</button>
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

.chat-toggle {
  position: fixed;
  bottom: 20px;
  right: 20px;
  width: 55px;
  height: 55px;
  border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #9333ea);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  cursor: pointer;
  box-shadow: 0 8px 20px rgba(0,0,0,0.2);
  z-index: 1000;
}

.chat-widget {
  position: fixed;
  bottom: 8px;
  left: 16px;
  width: 380px;
  height: 520px;
  background: #f3f4f6;
  border-radius: 18px;
  box-shadow: 0 15px 35px rgba(0,0,0,0.25);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  z-index: 1000;
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
  padding: 12px 14px;
  margin: 6px 0;
  border-radius: 14px;
  max-width: 80%;
  font-size: 1em;
  box-shadow: 0 3px 8px rgba(0,0,0,0.05);
}

.bot-message {
  background: white;
  align-self: flex-start;
}

.user-message {
  background: #e0e7ff;
  align-self: flex-end;
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
</style>
