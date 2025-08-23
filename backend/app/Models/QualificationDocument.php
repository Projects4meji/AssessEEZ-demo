<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class QualificationDocument extends Model
{
    use HasFactory, SoftDeletes;

    protected $fillable = [
        'id',
        'qualification_id',
        'document_title_id',
        'attachment',
        'comments',
        'status',
        'created_by',
        'updated_by',
        'created_at',
        'updated_at',
        'deleted_at',
        'iqa_status',
        'iqa_comment',
        'assessor_attachement'
    ];
}
