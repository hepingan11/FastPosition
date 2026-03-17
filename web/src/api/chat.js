import request from '@/utils/BSideRequest'

export function sendMessage(data) {
    return request({
        url: '/chat/message',
        method: 'post',
        data
    })
}

export function getChatHistory(sessionId) {
    return request({
        url: `/chat/history/${sessionId}`,
        method: 'get'
    })
}

export function clearChatSession(sessionId) {
    return request({
        url: `/chat/session/${sessionId}`,
        method: 'delete'
    })
}
