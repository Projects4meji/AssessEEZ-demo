<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class AssessorDocumentAttachement extends Model
{
    use HasFactory, SoftDeletes;

    protected $fillable = [
        'id',
        'assessor_document_id',
        'attachement',
        'created_by',
        'updated_by',
        'created_at',
        'updated_at',
        'deleted_at'
    ];
}
