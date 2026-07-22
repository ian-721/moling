package com.moling.livingnotebook.data.remote

/**
 * 后端地址暂时写成常量，本阶段不做设置页。
 * 真机测试：手机/平板要和运行 backend 的电脑在同一个局域网下，
 * 用这台电脑的局域网 IP（可用 ipconfig 查看，换网络后可能会变）。
 * 模拟器测试：改成 "http://10.0.2.2:8000"（模拟器访问主机 localhost 的固定地址）。
 */
object BackendConfig {
    const val BASE_URL = "http://10.133.101.225:8000"

    /**
     * 开发调试开关：ML Kit 识别失败时是否允许把纸面截图发给后端走 OpenAI Vision OCR fallback。
     * 默认 false —— Vision OCR 对中文手写会严重幻读，不允许作为默认路径。
     * 仅开发排查时手动改为 true。
     */
    const val ENABLE_VISION_FALLBACK_FOR_DEV = false
}
