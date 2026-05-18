const carousel = document.querySelector("[data-carousel]")
const prev_btn = document.querySelector("[data-carousel-prev]")
const next_btn = document.querySelector("[data-carousel-next]")
const dots_el = document.querySelector("[data-carousel-dots]")

let active_index = 0
let start_x = 0
let start_y = 0
let is_dragging = false

function get_cards() {
    return [...document.querySelectorAll(".report_card")]
}

function clamp_index(index, total) {
    if (total <= 0) {
        return 0
    }

    if (index < 0) {
        return 0
    }

    if (index >= total) {
        return total - 1
    }

    return index
}

function render_dots(cards) {
    dots_el.innerHTML = ""

    cards.forEach((card, index) => {
        const dot = document.createElement("button")
        dot.className = "carousel_dot"

        dot.addEventListener("click", () => {
            active_index = index
            update_carousel()
        })

        dots_el.appendChild(dot)
    })
}

function update_carousel() {
    const cards = get_cards()
    const dots = [...document.querySelectorAll(".carousel_dot")]

    if (!cards.length) {
        return
    }

    active_index = clamp_index(active_index, cards.length)

    cards.forEach((card, index) => {
        const offset = index - active_index
        const abs_offset = Math.abs(offset)

        const translate = offset * 46
        const scale = Math.max(0.72, 1 - abs_offset * 0.11)
        const opacity = Math.max(0, 1 - abs_offset * 0.34)
        const rotate = offset * -3
        const z_index = 100 - abs_offset

        card.style.transform = `translateX(calc(-50% + ${translate}%)) scale(${scale}) rotateY(${rotate}deg)`
        card.style.opacity = opacity
        card.style.zIndex = z_index
        card.style.filter = abs_offset === 0 ? "none" : "blur(0.4px)"
        card.style.pointerEvents = abs_offset <= 1 ? "auto" : "none"
    })

    dots.forEach((dot, index) => {
        dot.classList.toggle("is_active", index === active_index)
    })
}

function move_carousel(direction) {
    const cards = get_cards()

    active_index = clamp_index(active_index + direction, cards.length)
    update_carousel()
}

function on_pointer_down(event) {
    is_dragging = true
    start_x = event.clientX
    start_y = event.clientY
}

function on_pointer_up(event) {
    if (!is_dragging) {
        return
    }

    const diff_x = event.clientX - start_x
    const diff_y = event.clientY - start_y

    if (Math.abs(diff_x) > Math.abs(diff_y) && Math.abs(diff_x) > 60) {
        if (diff_x > 0) {
            move_carousel(-1)
        }

        if (diff_x < 0) {
            move_carousel(1)
        }
    }

    is_dragging = false
}

function on_card_click(event) {
    const cards = get_cards()
    const card = event.currentTarget
    const index = cards.indexOf(card)

    if (index === -1) {
        return
    }

    active_index = index
    update_carousel()
}

function copy_text(text) {
    if (navigator.clipboard && window.isSecureContext) {
        return navigator.clipboard.writeText(text)
    }

    const input = document.createElement("textarea")
    input.value = text
    input.setAttribute("readonly", "")
    input.style.position = "fixed"
    input.style.opacity = "0"

    document.body.appendChild(input)
    input.select()
    document.execCommand("copy")
    input.remove()

    return Promise.resolve()
}

function get_copy_toast() {
    let toast = document.querySelector(".copy_toast")

    if (!toast) {
        toast = document.createElement("div")
        toast.className = "copy_toast"
        document.body.appendChild(toast)
    }

    return toast
}

function show_copied(element) {
    const toast = get_copy_toast()
    const rect = element.getBoundingClientRect()

    element.classList.add("is_copied")

    toast.textContent = "Copied"
    toast.style.left = `${rect.left + rect.width / 2}px`
    toast.style.top = `${Math.max(12, rect.top - 10)}px`
    toast.classList.add("is_visible")

    setTimeout(() => {
        element.classList.remove("is_copied")
        toast.classList.remove("is_visible")
    }, 700)
}

function on_copy_colour_click(event) {
    const element = event.target.closest("[data-copy-colour]")

    if (!element) {
        return
    }

    event.preventDefault()
    event.stopPropagation()

    const colour = element.dataset.copyColour

    copy_text(colour).then(() => {
        show_copied(element)
    })
}

function init_copy_colours() {
    document.addEventListener("click", on_copy_colour_click, true)
}

function init_carousel() {
    const cards = get_cards()

    render_dots(cards)
    update_carousel()

    cards.forEach(card => {
        card.addEventListener("click", on_card_click)
    })

    if (prev_btn) {
        prev_btn.addEventListener("click", () => move_carousel(-1))
    }

    if (next_btn) {
        next_btn.addEventListener("click", () => move_carousel(1))
    }

    carousel.addEventListener("pointerdown", on_pointer_down)
    carousel.addEventListener("pointerup", on_pointer_up)
    carousel.addEventListener("pointercancel", () => {
        is_dragging = false
    })

    window.addEventListener("keydown", event => {
        if (event.key === "ArrowLeft") {
            move_carousel(-1)
        }

        if (event.key === "ArrowRight") {
            move_carousel(1)
        }
    })
}

init_carousel()
init_copy_colours()
