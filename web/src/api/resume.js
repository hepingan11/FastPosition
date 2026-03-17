import request from '@/utils/BSideRequest'

export function uploadResume(file, onUploadProgress) {
    const formData = new FormData()
    formData.append('file', file)
    return request({
        url: '/resume/upload',
        method: 'post',
        data: formData,
        headers: {
            'Content-Type': 'multipart/form-data'
        },
        onUploadProgress
    })
}

export function getResumes() {
    return request({
        url: '/resume/list',
        method: 'get'
    })
}

export function getResumeById(id) {
    return request({
        url: `/resume/${id}`,
        method: 'get'
    })
}

export function deleteResume(id) {
    return request({
        url: `/resume/${id}`,
        method: 'delete'
    })
}
